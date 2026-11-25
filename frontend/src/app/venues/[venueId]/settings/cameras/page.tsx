"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Camera, Lock, PenTool, Plus, RefreshCw, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, ApiError } from "@/lib/api";
import { hasCapability } from "@/lib/rbac";
import { useAuth } from "@/providers/AuthProvider";
import type { CameraItem } from "@/types/floor";

export default function CameraSettingsPage() {
  const params = useParams<{ venueId: string }>();
  const venueId = params?.venueId || "";
  const { user, loading: authLoading } = useAuth();
  const canManage = hasCapability(user?.role, "cameras.manage");

  const [cameras, setCameras] = useState<CameraItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [previewImg, setPreviewImg] = useState<{ name: string; b64: string } | null>(null);

  const [showModal, setShowModal] = useState(false);
  const [camName, setCamName] = useState("");
  const [streamType, setStreamType] = useState<"RTSP" | "RTSPS" | "DEMO_MP4">("RTSP");
  const [streamUrl, setStreamUrl] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [targetFps, setTargetFps] = useState(2);
  const [saving, setSaving] = useState(false);

  const loadCameras = useCallback(async () => {
    if (!venueId || !canManage) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{ items: CameraItem[] }>(
        `/api/v1/venues/${venueId}/cameras`,
      );
      setCameras(res.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load cameras");
    } finally {
      setLoading(false);
    }
  }, [venueId, canManage]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadCameras();
    }
  }, [authLoading, user, loadCameras]);

  async function handleAddCamera(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await apiFetch(`/api/v1/venues/${venueId}/cameras`, {
        method: "POST",
        body: JSON.stringify({
          name: camName.trim(),
          stream_type: streamType,
          stream_url: streamUrl.trim(),
          username: username.trim() || null,
          password: password || null,
          target_fps: targetFps,
          face_blur_enabled: true,
        }),
      });
      setSuccessMsg(`Added camera "${camName}".`);
      setCamName("");
      setStreamUrl("");
      setUsername("");
      setPassword("");
      setShowModal(false);
      await loadCameras();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add camera");
    } finally {
      setSaving(false);
    }
  }

  async function handleTestCamera(cam: CameraItem) {
    setTestingId(cam.id);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await apiFetch<{
        width: number;
        height: number;
        preview_jpeg_base64: string;
      }>(`/api/v1/venues/${venueId}/cameras/${cam.id}/test`, { method: "POST" });
      setPreviewImg({ name: cam.name, b64: res.preview_jpeg_base64 });
      setSuccessMsg(
        `Camera "${cam.name}" reachable (${res.width}×${res.height}, face-blurred preview verified).`,
      );
      await loadCameras();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Camera connectivity test failed");
    } finally {
      setTestingId(null);
    }
  }

  async function handleDeleteCamera(cam: CameraItem) {
    setError(null);
    try {
      await apiFetch(`/api/v1/venues/${venueId}/cameras/${cam.id}`, {
        method: "DELETE",
      });
      setSuccessMsg(`Removed camera "${cam.name}".`);
      await loadCameras();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to remove camera");
    }
  }

  return (
    <AppShell venueId={venueId}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Camera & RTSP Stream Management</h1>
            <p className="text-xs text-[var(--text-secondary)]">
              Encrypted RTSP/RTSPS ingestion with server-side SSRF validation & mandatory face blur
            </p>
          </div>
          {canManage && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void loadCameras()}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-2"
                aria-label="Refresh cameras"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => setShowModal((v) => !v)}
                className="inline-flex min-h-[38px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Add Camera
              </button>
            </div>
          )}
        </div>

        {!authLoading && user && !canManage && (
          <div className="tp-glass flex flex-col items-center gap-3 rounded-xl border p-8 text-center">
            <Lock className="h-8 w-8 text-amber-600" aria-hidden="true" />
            <h2 className="text-base font-bold">Permission Denied</h2>
            <p className="text-sm text-[var(--text-secondary)]">
              Camera settings require MANAGER or OWNER privileges.
            </p>
          </div>
        )}

        {successMsg && (
          <div role="status" className="rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">
            {successMsg}
          </div>
        )}
        {error && (
          <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800">
            {error}
          </div>
        )}

        {canManage && showModal && (
          <form
            onSubmit={handleAddCamera}
            className="tp-glass grid grid-cols-1 gap-3 rounded-xl border p-4 md:grid-cols-2"
          >
            <h2 className="md:col-span-2 text-sm font-bold">Add Camera Endpoint</h2>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Camera Name *
              <input
                type="text"
                required
                value={camName}
                onChange={(e) => setCamName(e.target.value)}
                placeholder="Main Dining North"
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Stream Type
              <select
                value={streamType}
                onChange={(e) =>
                  setStreamType(e.target.value as "RTSP" | "RTSPS" | "DEMO_MP4")
                }
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-sm"
              >
                <option value="RTSP">RTSP</option>
                <option value="RTSPS">RTSPS</option>
                <option value="DEMO_MP4">DEMO_MP4 (Demo mode only)</option>
              </select>
            </label>
            <label className="md:col-span-2 flex flex-col gap-1 text-xs font-medium">
              Stream URL *
              <input
                type="text"
                required
                value={streamUrl}
                onChange={(e) => setStreamUrl(e.target.value)}
                placeholder="rtsp://192.168.10.50:554/stream1"
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 font-mono text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Stream Username (Encrypted at rest)
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Stream Password (Never returned to browser)
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Target FPS (1–5)
              <input
                type="number"
                min={1}
                max={5}
                value={targetFps}
                onChange={(e) => setTargetFps(Number(e.target.value))}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-sm"
              />
            </label>
            <div className="flex items-end gap-2">
              <button
                type="submit"
                disabled={saving}
                className="min-h-[40px] flex-1 rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save Camera"}
              </button>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="min-h-[40px] rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-xs font-semibold"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {previewImg && (
          <div className="tp-glass rounded-xl border p-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-bold">Verified Face-Blurred Preview: {previewImg.name}</h2>
              <button
                type="button"
                onClick={() => setPreviewImg(null)}
                className="text-xs font-semibold text-[var(--accent-primary)]"
              >
                Dismiss
              </button>
            </div>
            {/* Dynamic base64 face-blurred camera frame */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`data:image/jpeg;base64,${previewImg.b64}`}
              alt={`Test snapshot for ${previewImg.name}`}
              className="max-h-72 rounded-lg object-contain"
            />
          </div>
        )}

        {canManage && loading && (
          <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
            Loading cameras...
          </div>
        )}

        {canManage && !loading && cameras.length === 0 && (
          <div className="tp-glass flex flex-col items-center gap-2 rounded-xl border p-8 text-center">
            <Camera className="h-8 w-8 text-[var(--text-secondary)]" aria-hidden="true" />
            <h2 className="text-base font-bold">No cameras configured</h2>
            <p className="text-xs text-[var(--text-secondary)]">
              Add an RTSP camera or DEMO_MP4 stream to start calibration.
            </p>
          </div>
        )}

        {canManage && cameras.length > 0 && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {cameras.map((cam) => (
              <article key={cam.id} className="tp-glass flex flex-col gap-3 rounded-xl border p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h2 className="text-base font-bold">{cam.name}</h2>
                    <p className="break-all font-mono text-xs text-[var(--text-secondary)]">
                      {cam.masked_stream_url || cam.stream_type}
                    </p>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                      cam.status === "ONLINE"
                        ? "bg-emerald-500/15 text-emerald-700"
                        : "bg-red-500/15 text-red-700"
                    }`}
                  >
                    {cam.status}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--text-secondary)]">
                  <span>{cam.stream_type}</span>
                  <span>·</span>
                  <span>{cam.target_fps} FPS</span>
                  <span>·</span>
                  <span className="inline-flex items-center gap-1 text-emerald-700">
                    <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                    Face Blur {cam.face_blur_enabled ? "On" : "Off"}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <button
                    type="button"
                    disabled={testingId === cam.id}
                    onClick={() => void handleTestCamera(cam)}
                    className="min-h-[38px] rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold hover:opacity-80 disabled:opacity-50"
                  >
                    {testingId === cam.id ? "Testing..." : "Test Connection"}
                  </button>
                  <Link
                    href={`/venues/${venueId}/settings/cameras/${cam.id}/calibrate`}
                    className="inline-flex min-h-[38px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white"
                  >
                    <PenTool className="h-3.5 w-3.5" aria-hidden="true" />
                    Calibrate Polygons
                  </Link>
                  <button
                    type="button"
                    onClick={() => void handleDeleteCamera(cam)}
                    className="ml-auto rounded-lg px-2.5 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50"
                  >
                    Remove
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
