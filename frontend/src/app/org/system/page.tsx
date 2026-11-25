"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Lock, Power, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, ApiError } from "@/lib/api";
import { hasCapability } from "@/lib/rbac";
import { useAuth } from "@/providers/AuthProvider";

interface SystemOverviewDTO {
  health: {
    api: string;
    postgres: string;
    valkey: string;
    cv_worker: string;
  };
  settings: {
    ai_inference_enabled: boolean;
    face_blur_enforced: boolean;
    snapshot_retention_days: number;
    analytics_retention_days: number;
  };
  models: Array<{
    id: string;
    model_role: string;
    version: string;
    artifact_uri: string;
    dataset_version: string;
    eval_metrics_json: Record<string, unknown>;
    gate_status: string;
    channel: string;
    is_active: boolean;
    created_at: string;
  }>;
}

export default function SystemHealthPage() {
  const { user, loading: authLoading } = useAuth();
  const canManageSystem = hasCapability(user?.role, "system.manage");

  const [data, setData] = useState<SystemOverviewDTO | null>(null);
  const [snapDays, setSnapDays] = useState(7);
  const [analyticsDays, setAnalyticsDays] = useState(365);
  const [confirmPurge, setConfirmPurge] = useState(false);

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadSystem = useCallback(async () => {
    if (!canManageSystem) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<SystemOverviewDTO>("/api/v1/org/system");
      setData(res);
      setSnapDays(res.settings.snapshot_retention_days);
      setAnalyticsDays(res.settings.analytics_retention_days);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load system overview");
    } finally {
      setLoading(false);
    }
  }, [canManageSystem]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadSystem();
    }
  }, [authLoading, user, loadSystem]);

  async function toggleKillSwitch() {
    if (!data) return;
    setBusy(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const nextEnabled = !data.settings.ai_inference_enabled;
      await apiFetch("/api/v1/org/system", {
        method: "PATCH",
        body: JSON.stringify({ ai_inference_enabled: nextEnabled }),
      });
      setSuccessMsg(
        nextEnabled
          ? "AI Inference Resumed across venue cameras."
          : "AI Inference Paused — Manual Floor Mode active.",
      );
      await loadSystem();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to toggle AI kill switch");
    } finally {
      setBusy(false);
    }
  }

  async function saveRetention(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await apiFetch("/api/v1/org/system", {
        method: "PATCH",
        body: JSON.stringify({
          snapshot_retention_days: snapDays,
          analytics_retention_days: analyticsDays,
        }),
      });
      setSuccessMsg("Updated retention policy.");
      await loadSystem();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update retention");
    } finally {
      setBusy(false);
    }
  }

  async function purgeSnapshotsNow() {
    setBusy(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await apiFetch<{ purged_files: number }>(
        "/api/v1/org/system/purge-snapshots",
        { method: "POST" },
      );
      setSuccessMsg(`Purged ${res.purged_files} review snapshots immediately.`);
      setConfirmPurge(false);
      await loadSystem();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to purge snapshots");
    } finally {
      setBusy(false);
    }
  }

  async function activateModel(modelId: string) {
    setBusy(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await apiFetch(`/api/v1/org/system/models/${modelId}/activate`, {
        method: "POST",
      });
      setSuccessMsg("Model version activated.");
      await loadSystem();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Model activation blocked");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell aiPaused={data ? !data.settings.ai_inference_enabled : false}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-xl font-bold tracking-tight">
              System Health, Model Registry & Privacy
            </h1>
            <p className="text-xs text-[var(--text-secondary)]">
              OWNER-only operational infrastructure status, ML release gate, AI kill switch, and retention purge
            </p>
          </div>
          {canManageSystem && (
            <button
              type="button"
              onClick={() => void loadSystem()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              Refresh
            </button>
          )}
        </div>

        {!authLoading && user && !canManageSystem && (
          <div className="tp-glass flex flex-col items-center gap-3 rounded-xl border p-8 text-center">
            <Lock className="h-8 w-8 text-amber-600" aria-hidden="true" />
            <h2 className="text-base font-bold">OWNER Access Required</h2>
            <p className="text-sm text-[var(--text-secondary)]">
              System Health, Model Activation, Kill Switch, and Privacy Purge are restricted to OWNER.
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

        {canManageSystem && loading && (
          <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
            Checking API, PostgreSQL, Valkey, and CV worker telemetry...
          </div>
        )}

        {canManageSystem && !loading && data && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Card 1: Service & Worker Health */}
            <section className="tp-glass flex flex-col gap-3 rounded-xl border p-4">
              <h2 className="text-base font-bold">Service & Worker Health</h2>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "FastAPI Backend", val: data.health.api },
                  { label: "PostgreSQL 16 + RLS", val: data.health.postgres },
                  { label: "Valkey 8 Streams", val: data.health.valkey },
                  { label: "CV Inference Worker", val: data.health.cv_worker },
                ].map((svc) => (
                  <div
                    key={svc.label}
                    className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-3"
                  >
                    <p className="text-xs text-[var(--text-secondary)]">{svc.label}</p>
                    <p
                      className={`mt-1 text-sm font-bold uppercase ${
                        svc.val === "ok" ? "text-emerald-800 dark:text-emerald-300" : "text-amber-800 dark:text-amber-300"
                      }`}
                    >
                      {svc.val}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            {/* Card 2: ML Model Registry & Evaluation */}
            <section className="tp-glass flex flex-col gap-3 rounded-xl border p-4">
              <h2 className="text-base font-bold">ML Model Registry & Evaluation</h2>
              <div className="space-y-2">
                {data.models.map((m) => (
                  <div
                    key={m.id}
                    className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-3 text-xs"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="font-mono font-bold">{m.version}</p>
                        <p className="text-[var(--text-secondary)]">
                          Channel: <strong>{m.channel}</strong> · Dataset: {m.dataset_version}
                        </p>
                      </div>
                      <span
                        className={`rounded-full px-2 py-0.5 font-bold ${
                          m.gate_status === "PASS"
                            ? "bg-emerald-100 text-emerald-900"
                            : "bg-amber-100 text-amber-900"
                        }`}
                      >
                        Gate: {m.gate_status}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold">
                        Offline TSM-F1:{" "}
                        {String(m.eval_metrics_json?.["TSM-F1"] ?? "NOT YET MEASURED")}
                      </span>
                      {!m.is_active ? (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void activateModel(m.id)}
                          className="rounded bg-[var(--accent-primary)] px-2.5 py-1 font-semibold text-white"
                        >
                          Activate Model
                        </button>
                      ) : (
                        <span className="rounded bg-emerald-100 px-2 py-0.5 font-semibold text-emerald-900">
                          Active
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Card 3: AI Pipeline Kill Switch */}
            <section className="tp-glass flex flex-col justify-between gap-3 rounded-xl border border-red-500/40 p-4">
              <div>
                <h2 className="text-base font-bold">AI Pipeline Kill Switch</h2>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  Immediately halts all automated camera frame inference and alerts across the
                  organization. Floor tables switch to manual operational updates until resumed.
                </p>
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={() => void toggleKillSwitch()}
                className={`inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-bold text-white disabled:opacity-50 ${
                  data.settings.ai_inference_enabled
                    ? "bg-red-700 hover:bg-red-800"
                    : "bg-emerald-700 hover:bg-emerald-800"
                }`}
              >
                <Power className="h-4 w-4" aria-hidden="true" />
                {data.settings.ai_inference_enabled
                  ? "Pause All AI Inference — Manual Mode Only"
                  : "Resume AI Inference"}
              </button>
            </section>

            {/* Card 4: Privacy & Data Retention */}
            <section className="tp-glass flex flex-col gap-3 rounded-xl border p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold">Privacy & Data Retention</h2>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-900">
                  <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                  Face Blur {data.settings.face_blur_enforced ? "ENFORCED" : "CUSTOM"}
                </span>
              </div>
              <form onSubmit={saveRetention} className="grid grid-cols-2 gap-2 text-xs font-medium">
                <label className="flex flex-col gap-1">
                  Review Crop TTL (days)
                  <input
                    type="number"
                    min={0}
                    max={30}
                    value={snapDays}
                    onChange={(e) => setSnapDays(Number(e.target.value))}
                    className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-sm"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  Analytics Retention (days)
                  <input
                    type="number"
                    min={30}
                    max={1095}
                    value={analyticsDays}
                    onChange={(e) => setAnalyticsDays(Number(e.target.value))}
                    className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-1.5 text-sm"
                  />
                </label>
                <button
                  type="submit"
                  disabled={busy}
                  className="col-span-2 mt-1 rounded-lg bg-[var(--accent-primary)] px-3 py-2 text-xs font-semibold text-white"
                >
                  Save Retention Policy
                </button>
              </form>

              <div className="border-t border-[var(--border-subtle)] pt-3">
                {!confirmPurge ? (
                  <button
                    type="button"
                    onClick={() => setConfirmPurge(true)}
                    className="inline-flex min-h-[40px] w-full items-center justify-center gap-2 rounded-lg bg-red-100 px-3 py-2 text-xs font-bold text-red-900 hover:bg-red-200"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    Purge All Snapshots Now
                  </button>
                ) : (
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void purgeSnapshotsNow()}
                      className="flex-1 rounded-lg bg-red-600 px-3 py-2 text-xs font-bold text-white"
                    >
                      Confirm Permanent Purge
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmPurge(false)}
                      className="rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-xs font-semibold"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            </section>
          </div>
        )}
      </div>
    </AppShell>
  );
}
