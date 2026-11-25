"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Check, ShieldCheck } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/providers/AuthProvider";

const STEPS = [
  "1 Venue Details",
  "2 Connect Camera",
  "3 Map Tables",
  "4 Alert Rules",
];

export default function OnboardingWizardPage() {
  const router = useRouter();
  const { user, demoMode, refreshSessionData } = useAuth();

  const [step, setStep] = useState(0);
  const [venueId, setVenueId] = useState<string | null>(null);
  const [cameraId, setCameraId] = useState<string | null>(null);

  // Step 1
  const [venueName, setVenueName] = useState("");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [hoursText, setHoursText] = useState("09:00 - 23:00");
  const [noticeAck, setNoticeAck] = useState(false);

  // Step 2
  const [camName, setCamName] = useState("Main Ceiling Cam");
  const [rtspUrl, setRtspUrl] = useState("");
  const [previewB64, setPreviewB64] = useState<string | null>(null);

  // Step 3
  const [mappedCount, setMappedCount] = useState(0);

  // Step 4
  const [serviceMin, setServiceMin] = useState(5);
  const [dirtyMin, setDirtyMin] = useState(2);

  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (user && user.role !== "OWNER") {
    return (
      <main className="min-h-screen flex items-center justify-center p-4">
        <div className="tp-card p-6 max-w-md text-center space-y-3">
          <h1 className="text-xl font-bold">Owner Permission Required</h1>
          <p className="text-sm text-[var(--tp-label-secondary)]">
            Only an organization OWNER can run venue onboarding.
          </p>
          <Link href="/" className="text-sm font-semibold text-[var(--tp-accent-text)]">
            Return Home
          </Link>
        </div>
      </main>
    );
  }

  const handleSaveVenue = async () => {
    if (!venueName.trim()) {
      setErrorMsg("Venue name is required.");
      return;
    }
    if (!noticeAck) {
      setErrorMsg("Please acknowledge operator responsibility for local CCTV signage/notices.");
      return;
    }
    setBusy(true);
    setErrorMsg(null);
    try {
      if (!venueId) {
        const created = await apiFetch<{ id: string }>("/api/v1/venues", {
          method: "POST",
          body: JSON.stringify({
            name: venueName.trim(),
            timezone,
            operating_hours_json: { default: hoursText },
          }),
        });
        setVenueId(created.id);
        await refreshSessionData();
      } else {
        await apiFetch(`/api/v1/venues/${venueId}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: venueName.trim(),
            timezone,
            operating_hours_json: { default: hoursText },
          }),
        });
      }
      setStep(1);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Failed to save venue");
    } finally {
      setBusy(false);
    }
  };

  const handleCameraTest = async (useDemo: boolean) => {
    if (!venueId) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      let cid = cameraId;
      if (!cid) {
        const cam = await apiFetch<{ id: string }>(`/api/v1/venues/${venueId}/cameras`, {
          method: "POST",
          body: JSON.stringify({
            name: camName.trim() || "Floor Camera 1",
            stream_type: useDemo ? "DEMO_MP4" : "RTSP",
            stream_url: useDemo ? "/app/data/demo/demo_floor.mp4" : rtspUrl.trim(),
            target_fps: 2,
            face_blur_enabled: true,
          }),
        });
        cid = cam.id;
        setCameraId(cid);
      }
      const testRes = await apiFetch<{ preview_jpeg_base64: string }>(
        `/api/v1/venues/${venueId}/cameras/${cid}/test`,
        { method: "POST" },
      );
      setPreviewB64(testRes.preview_jpeg_base64);
    } catch (err) {
      setErrorMsg(
        err instanceof ApiError
          ? `${err.message} (check RTSP credentials, port 554, and LAN firewall)`
          : "Camera connection failed",
      );
    } finally {
      setBusy(false);
    }
  };

  const handleQuickSampleTables = async () => {
    if (!venueId || !cameraId) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      const saved = await apiFetch<{ tables: Array<{ id: string }> }>(
        `/api/v1/venues/${venueId}/cameras/${cameraId}/polygons`,
        {
          method: "PUT",
          body: JSON.stringify({
            tables: [
              {
                table_code: "T01",
                section_name: "Main Hall",
                seat_capacity: 4,
                polygon_json: [
                  { x: 0.12, y: 0.2 },
                  { x: 0.28, y: 0.2 },
                  { x: 0.28, y: 0.38 },
                  { x: 0.12, y: 0.38 },
                ],
                floor_x: 0.2,
                floor_y: 0.3,
                shape: "RECT",
              },
              {
                table_code: "T02",
                section_name: "Main Hall",
                seat_capacity: 4,
                polygon_json: [
                  { x: 0.4, y: 0.2 },
                  { x: 0.58, y: 0.2 },
                  { x: 0.58, y: 0.38 },
                  { x: 0.4, y: 0.38 },
                ],
                floor_x: 0.5,
                floor_y: 0.3,
                shape: "RECT",
              },
              {
                table_code: "T03",
                section_name: "Main Hall",
                seat_capacity: 6,
                polygon_json: [
                  { x: 0.68, y: 0.2 },
                  { x: 0.86, y: 0.2 },
                  { x: 0.86, y: 0.38 },
                  { x: 0.68, y: 0.38 },
                ],
                floor_x: 0.8,
                floor_y: 0.3,
                shape: "BOOTH",
              },
            ],
            exclusion_polygons_json: [],
          }),
        },
      );
      setMappedCount(saved.tables.length);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Failed to save sample tables");
    } finally {
      setBusy(false);
    }
  };

  const handleLaunch = async () => {
    if (!venueId) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      await apiFetch(`/api/v1/venues/${venueId}/alert-rules`, {
        method: "PATCH",
        body: JSON.stringify({
          unattended_service_sec: serviceMin * 60,
          cleaning_alert_delay_sec: dirtyMin * 60,
        }),
      });
      await apiFetch("/api/v1/org/system", {
        method: "PATCH",
        body: JSON.stringify({ ai_inference_enabled: true }),
      });
      router.push(`/venues/${venueId}/floor`);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Launch failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen py-8 px-4 flex flex-col items-center">
      <div className="w-full max-w-[780px] space-y-5">
        <header>
          <h1 className="text-2xl font-bold">Venue Onboarding</h1>
          <p className="text-sm text-[var(--tp-label-secondary)]">
            Configure your restaurant branch, camera stream, table polygons, and service SLAs.
          </p>
        </header>

        {/* Stepper Pills */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 tp-glass rounded-[28px] p-2">
          {STEPS.map((label, idx) => {
            const active = idx === step;
            const done = idx < step;
            return (
              <button
                key={label}
                type="button"
                aria-current={active ? "step" : undefined}
                onClick={() => {
                  if (idx <= step || venueId) setStep(idx);
                }}
                className={`min-h-[44px] rounded-full px-3 text-xs font-semibold flex items-center justify-center gap-1.5 ${
                  active
                    ? "bg-[var(--tp-accent)] text-white"
                    : done
                      ? "bg-[#34C759]/16 text-[#146C2E] dark:text-[#6EE787]"
                      : "text-[var(--tp-label-secondary)]"
                }`}
              >
                {done && <Check className="h-3.5 w-3.5" aria-hidden="true" />}
                <span>{label}</span>
              </button>
            );
          })}
        </div>

        {errorMsg && (
          <div
            role="alert"
            className="rounded-2xl bg-[#FF3B30]/14 px-4 py-3 text-xs font-semibold text-[#B42318] dark:text-[#FF8A80]"
          >
            {errorMsg}
          </div>
        )}

        <section className="tp-card p-6 space-y-4">
          {step === 0 && (
            <>
              <div>
                <label htmlFor="ob-venue-name" className="block text-xs font-semibold mb-1.5">
                  Venue Name
                </label>
                <input
                  id="ob-venue-name"
                  value={venueName}
                  onChange={(e) => setVenueName(e.target.value)}
                  placeholder="Downtown Bistro"
                  className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="ob-tz" className="block text-xs font-semibold mb-1.5">
                    Timezone
                  </label>
                  <select
                    id="ob-tz"
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
                  >
                    <option value="UTC">UTC</option>
                    <option value="Asia/Kolkata">Asia/Kolkata</option>
                    <option value="America/New_York">America/New_York</option>
                    <option value="America/Los_Angeles">America/Los_Angeles</option>
                    <option value="Europe/London">Europe/London</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="ob-hours" className="block text-xs font-semibold mb-1.5">
                    Operating Hours
                  </label>
                  <input
                    id="ob-hours"
                    value={hoursText}
                    onChange={(e) => setHoursText(e.target.value)}
                    className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
                  />
                </div>
              </div>
              <div className="rounded-2xl bg-[#34C759]/14 p-4 flex items-center justify-between">
                <div className="flex items-center gap-2.5 text-sm font-semibold text-[#146C2E] dark:text-[#6EE787]">
                  <ShieldCheck className="h-5 w-5" aria-hidden="true" />
                  Privacy Face Blur (ON by default, audio stripped)
                </div>
                <span className="rounded-full bg-emerald-700 text-white px-2.5 py-0.5 text-xs font-bold">
                  ON
                </span>
              </div>
              <label className="flex items-start gap-3 text-xs text-[var(--tp-label-secondary)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={noticeAck}
                  onChange={(e) => setNoticeAck(e.target.checked)}
                  className="mt-0.5 h-5 w-5"
                />
                <span>
                  I confirm that our venue is responsible for posting required CCTV &amp; privacy notices for guests and staff (starter EN/HI templates in <code>docs/templates/</code>).
                </span>
              </label>
            </>
          )}

          {step === 1 && (
            <>
              <div>
                <label htmlFor="ob-cam-name" className="block text-xs font-semibold mb-1.5">
                  Camera Name
                </label>
                <input
                  id="ob-cam-name"
                  value={camName}
                  onChange={(e) => setCamName(e.target.value)}
                  className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
                />
              </div>
              <div>
                <label htmlFor="ob-rtsp" className="block text-xs font-semibold mb-1.5">
                  RTSP / RTSPS URL
                </label>
                <input
                  id="ob-rtsp"
                  value={rtspUrl}
                  onChange={(e) => setRtspUrl(e.target.value)}
                  placeholder="rtsp://192.168.1.40:554/stream1"
                  className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm font-mono border border-[var(--tp-card-border)]"
                />
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={busy || !rtspUrl.trim()}
                  onClick={() => handleCameraTest(false)}
                  className="min-h-[44px] rounded-full bg-[var(--tp-accent)] px-5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {busy ? "Testing..." : "Test Connection"}
                </button>
                {demoMode && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => handleCameraTest(true)}
                    className="min-h-[44px] rounded-full bg-[var(--tp-inset-field)] px-5 text-sm font-semibold border border-[var(--tp-card-border)]"
                  >
                    Load Sample Restaurant Video
                  </button>
                )}
              </div>
              {previewB64 && (
                <div className="rounded-2xl overflow-hidden border border-[var(--tp-card-border)] bg-black">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`data:image/jpeg;base64,${previewB64}`}
                    alt="Face-blurred camera preview"
                    className="w-full aspect-video object-cover"
                  />
                </div>
              )}
            </>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <p className="text-sm text-[var(--tp-label-secondary)]">
                Map your dining table polygons onto the camera snapshot. You can initialize 3 starter tables now or open the full interactive polygon editor.
              </p>
              <div className="text-sm font-semibold">
                Mapped Polygons: {mappedCount} tables
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={busy || !cameraId}
                  onClick={handleQuickSampleTables}
                  className="min-h-[44px] rounded-full bg-[var(--tp-accent)] px-5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {busy ? "Saving..." : "Initialize Starter Tables (T01–T03)"}
                </button>
                {venueId && cameraId && (
                  <Link
                    href={`/venues/${venueId}/settings/cameras/${cameraId}/calibrate`}
                    className="inline-flex min-h-[44px] items-center rounded-full bg-[var(--tp-inset-field)] px-5 text-sm font-semibold border border-[var(--tp-card-border)]"
                  >
                    Open Full Polygon Editor
                  </Link>
                )}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="ob-service" className="block text-xs font-semibold mb-1.5">
                  Unattended Service Alert (minutes, 1–30)
                </label>
                <input
                  id="ob-service"
                  type="number"
                  min={1}
                  max={30}
                  value={serviceMin}
                  onChange={(e) => setServiceMin(Number(e.target.value))}
                  className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
                />
              </div>
              <div>
                <label htmlFor="ob-dirty" className="block text-xs font-semibold mb-1.5">
                  Dirty Table Alert Delay (minutes, 0–15)
                </label>
                <input
                  id="ob-dirty"
                  type="number"
                  min={0}
                  max={15}
                  value={dirtyMin}
                  onChange={(e) => setDirtyMin(Number(e.target.value))}
                  className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
                />
              </div>
            </div>
          )}

          <div className="pt-4 border-t border-[var(--tp-separator)] flex flex-wrap items-center justify-between gap-3">
            <button
              type="button"
              disabled={step === 0 || busy}
              onClick={() => setStep((s) => Math.max(0, s - 1))}
              className="min-h-[44px] rounded-full px-5 text-sm font-semibold bg-[var(--tp-inset-field)] disabled:opacity-40"
            >
              Back
            </button>
            <div className="flex items-center gap-3">
              {venueId && step > 0 && step < 3 && (
                <button
                  type="button"
                  onClick={() => router.push(`/venues/${venueId}/floor`)}
                  className="min-h-[44px] rounded-full px-4 text-sm font-semibold text-[var(--tp-label-secondary)]"
                >
                  Skip for now
                </button>
              )}
              {step === 0 && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={handleSaveVenue}
                  className="min-h-[44px] rounded-full bg-[var(--tp-accent)] px-6 text-sm font-semibold text-white"
                >
                  {busy ? "Saving..." : "Continue"}
                </button>
              )}
              {step > 0 && step < 3 && (
                <button
                  type="button"
                  onClick={() => setStep((s) => s + 1)}
                  className="min-h-[44px] rounded-full bg-[var(--tp-accent)] px-6 text-sm font-semibold text-white"
                >
                  Continue
                </button>
              )}
              {step === 3 && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={handleLaunch}
                  className="min-h-[44px] rounded-full bg-emerald-700 px-6 text-sm font-semibold text-white"
                >
                  {busy ? "Launching..." : "Launch Live Floor"}
                </button>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
