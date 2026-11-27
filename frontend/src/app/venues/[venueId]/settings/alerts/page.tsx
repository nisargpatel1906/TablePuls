"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Lock, Save, Send } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, ApiError } from "@/lib/api";
import { hasCapability } from "@/lib/rbac";
import { useAuth } from "@/providers/AuthProvider";

interface AlertRuleDTO {
  id: string;
  venue_id: string;
  section_name: string | null;
  unattended_service_sec: number;
  cleaning_alert_delay_sec: number;
  occupancy_debounce_sec: number;
  departure_debounce_sec: number;
  min_confidence: number;
  require_bussing_confirmation: boolean;
  has_webhook_url: boolean;
  quiet_hours_enabled: boolean;
}

export default function AlertRulesSettingsPage() {
  const params = useParams<{ venueId: string }>();
  const venueId = params?.venueId || "";
  const { user, loading: authLoading } = useAuth();
  const canManage = hasCapability(user?.role, "alert_rules.manage");

  const [tab, setTab] = useState<"thresholds" | "channels" | "quiet">("thresholds");
  const [rule, setRule] = useState<AlertRuleDTO | null>(null);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingWebhook, setTestingWebhook] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadRules = useCallback(async () => {
    if (!venueId || !canManage) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{ items: AlertRuleDTO[] }>(
        `/api/v1/venues/${venueId}/alert-rules`,
      );
      const first = res.items[0] || null;
      setRule(
        first
          ? { ...first, min_confidence: Math.round(first.min_confidence * 100) / 100 }
          : null,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load alert rules");
    } finally {
      setLoading(false);
    }
  }, [venueId, canManage]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadRules();
    }
  }, [authLoading, user, loadRules]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!rule) return;
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const payload: Record<string, unknown> = {
        unattended_service_sec: rule.unattended_service_sec,
        cleaning_alert_delay_sec: rule.cleaning_alert_delay_sec,
        occupancy_debounce_sec: rule.occupancy_debounce_sec,
        departure_debounce_sec: rule.departure_debounce_sec,
        min_confidence: Math.round(rule.min_confidence * 100) / 100,
        require_bussing_confirmation: rule.require_bussing_confirmation,
        quiet_hours_enabled: rule.quiet_hours_enabled,
      };
      if (webhookUrl.trim()) payload.webhook_url = webhookUrl.trim();
      if (webhookSecret.trim()) payload.webhook_secret = webhookSecret.trim();

      const updated = await apiFetch<AlertRuleDTO>(
        `/api/v1/venues/${venueId}/alert-rules`,
        {
          method: "PATCH",
          body: JSON.stringify(payload),
        },
      );
      setRule(updated);
      setWebhookUrl("");
      setWebhookSecret("");
      setSuccessMsg("Saved alert thresholds and channel rules.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save alert rules");
    } finally {
      setSaving(false);
    }
  }

  async function handleTestWebhook() {
    setTestingWebhook(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await apiFetch<{ http_status: number; detail: string }>(
        `/api/v1/venues/${venueId}/alert-rules/test-webhook`,
        {
          method: "POST",
          body: JSON.stringify({
            webhook_url: webhookUrl.trim() || null,
            webhook_secret: webhookSecret.trim() || null,
          }),
        },
      );
      setSuccessMsg(`Test webhook delivered (HTTP ${res.http_status}): ${res.detail}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Webhook delivery failed");
    } finally {
      setTestingWebhook(false);
    }
  }

  return (
    <AppShell venueId={venueId}>
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Alert Rules & Threshold Settings</h1>
          <p className="text-xs text-[var(--text-secondary)]">
            Tune CV debounce windows, service SLA alerts, and HMAC-signed webhooks
          </p>
        </div>

        {!authLoading && user && !canManage && (
          <div className="tp-glass flex flex-col items-center gap-3 rounded-xl border p-8 text-center">
            <Lock className="h-8 w-8 text-amber-600" aria-hidden="true" />
            <h2 className="text-base font-bold">Permission Denied</h2>
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

        {canManage && !loading && rule && (
          <form onSubmit={handleSave} className="tp-glass flex max-w-3xl flex-col gap-4 rounded-xl border p-4">
            <div className="flex flex-wrap gap-2 border-b border-[var(--border-subtle)] pb-3" role="tablist">
              {(["thresholds", "channels", "quiet"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  role="tab"
                  aria-selected={tab === k}
                  onClick={() => setTab(k)}
                  className={`rounded-full px-3 py-1.5 text-xs font-semibold capitalize ${
                    tab === k
                      ? "bg-[var(--accent-primary)] text-white"
                      : "border border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                  }`}
                >
                  {k === "thresholds"
                    ? "Thresholds"
                    : k === "channels"
                      ? "Notification Channels"
                      : "Quiet Hours"}
                </button>
              ))}
            </div>

            {tab === "thresholds" && (
              <div className="space-y-4">
                {[
                  {
                    key: "unattended_service_sec" as const,
                    label: "Unattended Service Alert Delay (sec)",
                    min: 60,
                    max: 1800,
                    step: 10,
                  },
                  {
                    key: "cleaning_alert_delay_sec" as const,
                    label: "Dirty Table / Bussing Delay (sec)",
                    min: 30,
                    max: 900,
                    step: 5,
                  },
                  {
                    key: "occupancy_debounce_sec" as const,
                    label: "Occupancy Debounce (sec)",
                    min: 3,
                    max: 60,
                    step: 1,
                  },
                  {
                    key: "departure_debounce_sec" as const,
                    label: "Departure Debounce (sec)",
                    min: 5,
                    max: 120,
                    step: 1,
                  },
                ].map((cfg) => (
                  <div
                    key={cfg.key}
                    className="flex flex-col gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-3 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <label htmlFor={`num-${cfg.key}`} className="text-xs font-semibold">
                      {cfg.label}
                    </label>
                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        aria-label={cfg.label}
                        min={cfg.min}
                        max={cfg.max}
                        step={cfg.step}
                        value={rule[cfg.key]}
                        onChange={(e) =>
                          setRule({ ...rule, [cfg.key]: Number(e.target.value) })
                        }
                        className="accent-[var(--accent-primary)]"
                      />
                      <input
                        id={`num-${cfg.key}`}
                        type="number"
                        min={cfg.min}
                        max={cfg.max}
                        value={rule[cfg.key]}
                        onChange={(e) =>
                          setRule({ ...rule, [cfg.key]: Number(e.target.value) })
                        }
                        className="w-20 rounded border border-[var(--border-subtle)] bg-[var(--bg-canvas)] px-2 py-1 text-right font-mono text-xs"
                      />
                    </div>
                  </div>
                ))}

                <div className="flex flex-col gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-3 sm:flex-row sm:items-center sm:justify-between">
                  <label htmlFor="min-conf-input" className="text-xs font-semibold">
                    Minimum Detection Confidence (0.30–0.95)
                  </label>
                  <input
                    id="min-conf-input"
                    type="number"
                    step="any"
                    min={0.3}
                    max={0.95}
                    value={rule.min_confidence}
                    onChange={(e) =>
                      setRule({ ...rule, min_confidence: Number(e.target.value) })
                    }
                    className="w-24 rounded border border-[var(--border-subtle)] bg-[var(--bg-canvas)] px-2 py-1 text-right font-mono text-xs"
                  />
                </div>

                <label className="flex min-h-[44px] items-center gap-2 text-xs font-medium md:min-h-0">
                  <input
                    type="checkbox"
                    checked={rule.require_bussing_confirmation}
                    onChange={(e) =>
                      setRule({ ...rule, require_bussing_confirmation: e.target.checked })
                    }
                  />
                  Require manual bussing confirmation before leaving NEEDS_CLEANING
                </label>
              </div>
            )}

            {tab === "channels" && (
              <div className="space-y-3">
                <p className="text-xs text-[var(--text-secondary)]">
                  Status: {rule.has_webhook_url ? "Webhook URL configured (encrypted)" : "Not configured"} ·
                  Deliveries require WEBHOOKS_ENABLED=true and are SSRF-checked on save and delivery.
                </p>
                <label className="flex flex-col gap-1 text-xs font-medium">
                  HTTPS Webhook URL (replace existing)
                  <input
                    type="url"
                    value={webhookUrl}
                    onChange={(e) => setWebhookUrl(e.target.value)}
                    placeholder="https://hooks.example.com/tablepulse"
                    className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 font-mono text-sm"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium">
                  HMAC-SHA256 Signing Secret
                  <input
                    type="password"
                    value={webhookSecret}
                    onChange={(e) => setWebhookSecret(e.target.value)}
                    placeholder="Minimum 16 chars recommended"
                    className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-2 text-sm"
                  />
                </label>
                <button
                  type="button"
                  disabled={testingWebhook}
                  onClick={() => void handleTestWebhook()}
                  className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold"
                >
                  <Send className="h-3.5 w-3.5" aria-hidden="true" />
                  {testingWebhook ? "Sending..." : "Send Test Webhook"}
                </button>
              </div>
            )}

            {tab === "quiet" && (
              <div className="space-y-3">
                <label className="flex min-h-[44px] items-center gap-2 text-sm font-medium md:min-h-0">
                  <input
                    type="checkbox"
                    checked={rule.quiet_hours_enabled}
                    onChange={(e) =>
                      setRule({ ...rule, quiet_hours_enabled: e.target.checked })
                    }
                  />
                  Enable quiet hours outside active venue operating hours
                </label>
                <p className="text-xs text-[var(--text-secondary)]">
                  When quiet hours are enabled, outbound webhook notifications are suppressed while floor state recording continues.
                </p>
              </div>
            )}

            <button
              type="submit"
              disabled={saving}
              className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              <Save className="h-4 w-4" aria-hidden="true" />
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </form>
        )}
      </div>
    </AppShell>
  );
}
