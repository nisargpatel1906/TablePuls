"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Lock, RefreshCw, ShieldCheck, Video } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, ApiError } from "@/lib/api";
import { hasCapability } from "@/lib/rbac";
import { formatElapsed, TABLE_STATE_META } from "@/lib/table-states";
import { useAuth } from "@/providers/AuthProvider";
import type { CameraItem, FloorTable } from "@/types/floor";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PreviewPayload {
  camera_id: string;
  status: string;
  width: number;
  height: number;
  face_blurred: boolean;
  preview_jpeg_base64: string;
}

function WhepVideo({
  whepUrl,
  cameraName,
  fallback,
}: {
  whepUrl: string;
  cameraName: string;
  fallback: React.ReactNode;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [liveReady, setLiveReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let pc: RTCPeerConnection | null = null;
    async function startWhep() {
      if (typeof RTCPeerConnection === "undefined") return;
      try {
        pc = new RTCPeerConnection();
        pc.addTransceiver("video", { direction: "recvonly" });
        pc.ontrack = (ev) => {
          if (cancelled || !videoRef.current) return;
          if (ev.streams[0]) {
            videoRef.current.srcObject = ev.streams[0];
            setLiveReady(true);
          }
        };
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        const resp = await fetch(whepUrl, {
          method: "POST",
          headers: { "Content-Type": "application/sdp" },
          body: offer.sdp,
        });
        if (!resp.ok || cancelled) return;
        const answerSdp = await resp.text();
        await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
      } catch {
        if (!cancelled) setLiveReady(false);
      }
    }
    void startWhep();
    return () => {
      cancelled = true;
      pc?.close();
    };
  }, [whepUrl]);

  return (
    <>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        aria-label={`Live WebRTC stream for ${cameraName}`}
        className={`h-full w-full object-cover ${liveReady ? "block" : "hidden"}`}
      />
      {!liveReady && fallback}
    </>
  );
}

export default function LiveCameraWallPage() {
  const params = useParams<{ venueId: string }>();
  const venueId = params?.venueId || "";
  const { user, venues, loading: authLoading } = useAuth();
  const activeVenue = venues.find((v) => v.id === venueId) || venues[0];

  const canViewCameras = hasCapability(
    user?.role,
    "cameras.live.view",
    Boolean(activeVenue?.allow_host_camera_view),
  );

  const [cameras, setCameras] = useState<CameraItem[]>([]);
  const [tables, setTables] = useState<FloorTable[]>([]);
  const [previews, setPreviews] = useState<Record<string, PreviewPayload>>({});
  const [streamTokens, setStreamTokens] = useState<
    Record<string, { whepUrl?: string; mjpegUrl: string }>
  >({});
  const [displayFps, setDisplayFps] = useState<24 | 30 | 60>(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gridCols, setGridCols] = useState<1 | 2>(2);
  const [showPolygons, setShowPolygons] = useState(true);
  const [showTimers, setShowTimers] = useState(true);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const t = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  const refreshPreviews = useCallback(
    async (camList: CameraItem[]) => {
      if (!venueId || camList.length === 0) return;
      const nextPreviews: Record<string, PreviewPayload> = {};
      await Promise.all(
        camList.map(async (cam) => {
          try {
            const snap = await apiFetch<PreviewPayload>(
              `/api/v1/venues/${venueId}/cameras/${cam.id}/preview`,
            );
            nextPreviews[cam.id] = snap;
          } catch {
            // Camera offline / unreachable shown cleanly on card
          }
        }),
      );
      setPreviews((prev) => ({ ...prev, ...nextPreviews }));
    },
    [venueId],
  );

  const loadFeeds = useCallback(async () => {
    if (!venueId || !canViewCameras) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [camRes, floorRes] = await Promise.all([
        apiFetch<{ items: CameraItem[] }>(`/api/v1/venues/${venueId}/cameras`),
        apiFetch<{ tables: FloorTable[] }>(`/api/v1/venues/${venueId}/floor-state`),
      ]);
      setCameras(camRes.items);
      setTables(floorRes.tables);
      // Issue live stream tokens immediately for ONLINE cameras so they stream at Display FPS (24/30/60)
      const onlineCams = camRes.items.filter((c) => c.status === "ONLINE");
      if (onlineCams.length > 0) {
        void Promise.all(
          onlineCams.map(async (c) => {
            try {
              const tok = await apiFetch<{ whep_url: string; mjpeg_url: string }>(
                `/api/v1/venues/${venueId}/cameras/${c.id}/stream-token`,
                { method: "POST" },
              );
              setStreamTokens((prev) => ({
                ...prev,
                [c.id]: { mjpegUrl: `${API_BASE}${tok.mjpeg_url}` },
              }));
            } catch {
              // Fallback to /preview if token issuance fails
            }
          }),
        );
      }
      // Fetch initial /preview snapshots in background (only for cameras without an active live stream)
      const previewCams = camRes.items.filter((c) => c.status !== "ONLINE");
      if (previewCams.length > 0) {
        void refreshPreviews(previewCams);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load cameras");
    } finally {
      setLoading(false);
    }
  }, [venueId, canViewCameras, refreshPreviews]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadFeeds();
    }
  }, [authLoading, user, loadFeeds]);

  // Periodically refresh blurred snapshots only for cameras without an active live MJPEG/WebRTC stream
  useEffect(() => {
    if (!canViewCameras || cameras.length === 0) return;
    const t = window.setInterval(() => {
      const pending = cameras.filter((c) => !streamTokens[c.id]);
      if (pending.length > 0) {
        void refreshPreviews(pending);
      }
    }, 4000);
    return () => window.clearInterval(t);
  }, [canViewCameras, cameras, streamTokens, refreshPreviews]);

  async function requestWhepToken(cameraId: string) {
    try {
      const tok = await apiFetch<{ whep_url: string; mjpeg_url: string }>(
        `/api/v1/venues/${venueId}/cameras/${cameraId}/stream-token`,
        { method: "POST" },
      );
      setStreamTokens((prev) => ({
        ...prev,
        [cameraId]: { whepUrl: tok.whep_url, mjpegUrl: `${API_BASE}${tok.mjpeg_url}` },
      }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to issue stream token");
    }
  }

  return (
    <AppShell venueId={venueId}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Live Camera Wall</h1>
            <p className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
              Privacy Shield Active: Face Blur Enforced & Audio Stripped via MediaMTX WHEP
            </p>
          </div>
          {canViewCameras && (
            <div className="flex flex-wrap items-center gap-2">
              <label className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-medium md:min-h-0">
                <input
                  type="checkbox"
                  checked={showPolygons}
                  onChange={(e) => setShowPolygons(e.target.checked)}
                />
                Show Table Polygons
              </label>
              <label className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-xs font-medium md:min-h-0">
                <input
                  type="checkbox"
                  checked={showTimers}
                  onChange={(e) => setShowTimers(e.target.checked)}
                />
                Show Dwell Timers
              </label>
              <label className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1 text-xs font-semibold md:min-h-0">
                <span>Display FPS</span>
                <select
                  aria-label="Live display FPS"
                  value={displayFps}
                  onChange={(e) => setDisplayFps(Number(e.target.value) as 24 | 30 | 60)}
                  className="bg-transparent text-xs font-bold outline-none"
                >
                  <option value={24}>24 FPS</option>
                  <option value={30}>30 FPS</option>
                  <option value={60}>60 FPS</option>
                </select>
              </label>
              <button
                type="button"
                onClick={() => setGridCols((c) => (c === 2 ? 1 : 2))}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold"
              >
                Grid: {gridCols === 2 ? "2×2" : "1×1"}
              </button>
              <button
                type="button"
                onClick={() => void loadFeeds()}
                className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                Refresh Feeds
              </button>
            </div>
          )}
        </div>

        {!authLoading && user && !canViewCameras && (
          <div className="tp-glass flex flex-col items-center gap-3 rounded-xl border p-8 text-center">
            <Lock className="h-8 w-8 text-amber-600" aria-hidden="true" />
            <h2 className="text-base font-bold">Permission Denied</h2>
            <p className="text-sm text-[var(--text-secondary)]">
              Live camera wall access is disabled for your role in this venue.
            </p>
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800"
          >
            {error}
          </div>
        )}

        {canViewCameras && loading && cameras.length === 0 && (
          <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
            Connecting to MediaMTX camera feeds...
          </div>
        )}

        {canViewCameras && !loading && cameras.length === 0 && (
          <div className="tp-glass rounded-xl border p-8 text-center">
            <Video className="mx-auto h-8 w-8 text-[var(--text-secondary)]" aria-hidden="true" />
            <h2 className="mt-2 text-base font-bold">No cameras configured</h2>
            <Link
              href={`/venues/${venueId}/settings/cameras`}
              className="mt-3 inline-block rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white"
            >
              Add Camera
            </Link>
          </div>
        )}

        {canViewCameras && cameras.length > 0 && (
          <div
            className={`grid grid-cols-1 gap-4 ${gridCols === 2 ? "lg:grid-cols-2" : ""}`}
          >
            {cameras.map((cam) => {
              const preview = previews[cam.id];
              const camTables = tables.filter((t) => t.camera_id === cam.id);
              const tokens = streamTokens[cam.id];
              const whepUrl = tokens?.whepUrl;
              const liveMjpegUrl = tokens?.mjpegUrl ? `${tokens.mjpegUrl}&fps=${displayFps}` : null;
              const fallbackNode = liveMjpegUrl ? (
                // High-FPS face-blurred multipart MJPEG live stream
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={liveMjpegUrl}
                  alt={`Live ${displayFps} FPS face-blurred stream for ${cam.name}`}
                  className="h-full w-full object-cover"
                />
              ) : preview ? (
                // Dynamic base64 face-blurred camera frame cannot use static next/image
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={`data:image/jpeg;base64,${preview.preview_jpeg_base64}`}
                  alt={`Face-blurred camera preview for ${cam.name}`}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full items-end justify-start p-2.5 text-left text-[11px] text-slate-200">
                  <span className="rounded-md bg-slate-950/80 px-2.5 py-1 backdrop-blur-sm">
                    {loading
                      ? `Loading privacy-blurred preview for ${cam.name}...`
                      : `Camera feed unavailable (${cam.status}). Verify RTSP/MediaMTX connectivity.`}
                  </span>
                </div>
              );

              return (
                <article
                  key={cam.id}
                  className="tp-glass overflow-hidden rounded-xl border p-3"
                >
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div>
                      <h2 className="text-sm font-bold">{cam.name}</h2>
                      <p className="text-[11px] text-[var(--text-secondary)]">
                        {cam.stream_type} · Display: {displayFps} FPS · ML: {cam.target_fps} FPS · Status: {cam.status}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void requestWhepToken(cam.id)}
                      className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1 text-xs font-semibold hover:opacity-80"
                    >
                      {whepUrl ? "WHEP Token Issued" : "Issue WHEP Token"}
                    </button>
                  </div>

                  <div className="relative aspect-video w-full overflow-hidden rounded-lg bg-slate-900">
                    {whepUrl ? (
                      <WhepVideo
                        whepUrl={whepUrl}
                        cameraName={cam.name}
                        fallback={fallbackNode}
                      />
                    ) : (
                      fallbackNode
                    )}

                    {showPolygons && camTables.length > 0 && (
                      <svg
                        viewBox="0 0 100 100"
                        preserveAspectRatio="none"
                        className="pointer-events-none absolute inset-0 h-full w-full"
                        aria-hidden="true"
                      >
                        {camTables.map((tbl) => {
                          const pts = (tbl.polygon_json || [])
                            .map((p) => `${p.x * 100},${p.y * 100}`)
                            .join(" ");
                          const meta =
                            TABLE_STATE_META[tbl.current_state] ?? TABLE_STATE_META.UNKNOWN;
                          const cx =
                            tbl.polygon_json.length > 0
                              ? (tbl.polygon_json.reduce((a, p) => a + p.x, 0) /
                                  tbl.polygon_json.length) *
                                100
                              : 50;
                          const cy =
                            tbl.polygon_json.length > 0
                              ? (tbl.polygon_json.reduce((a, p) => a + p.y, 0) /
                                  tbl.polygon_json.length) *
                                100
                              : 50;
                          const timerText =
                            showTimers && tbl.occupied_since
                              ? formatElapsed(tbl.occupied_since, nowMs)
                              : "";
                          const pillWidth = timerText ? 14 : 7.5;
                          const pillHeight = timerText ? 6.8 : 4;
                          return pts ? (
                            <g key={tbl.id}>
                              <polygon
                                points={pts}
                                fill={meta.accentHex + "33"}
                                stroke={meta.accentHex}
                                strokeWidth="0.6"
                              />
                              <rect
                                x={cx - pillWidth / 2}
                                y={cy - pillHeight / 2}
                                width={pillWidth}
                                height={pillHeight}
                                rx="1"
                                fill="rgba(15, 23, 42, 0.78)"
                              />
                              <text
                                x={cx}
                                y={timerText ? cy - 1.1 : cy}
                                fill="#FFFFFF"
                                fontSize="2.5"
                                fontWeight="bold"
                                textAnchor="middle"
                                dominantBaseline="middle"
                              >
                                {tbl.table_code}
                              </text>
                              {timerText && (
                                <text
                                  x={cx}
                                  y={cy + 1.7}
                                  fill="#E2E8F0"
                                  fontSize="2.1"
                                  fontWeight="600"
                                  textAnchor="middle"
                                  dominantBaseline="middle"
                                >
                                  {timerText}
                                </text>
                              )}
                            </g>
                          ) : null;
                        })}
                      </svg>
                    )}
                  </div>

                  {whepUrl && (
                    <p className="mt-2 truncate font-mono text-[11px] text-[var(--text-secondary)]">
                      WHEP endpoint ready (short-lived token signed; blurred frame relay active)
                    </p>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}
