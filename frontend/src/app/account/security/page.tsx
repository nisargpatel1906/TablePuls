"use client";

import React, { useState } from "react";
import { Check, Copy, Download, KeyRound, ShieldAlert, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/providers/AuthProvider";

interface EnrollPayload {
  enroll_token: string;
  secret: string;
  provisioning_uri: string;
  qr_svg_data_uri: string;
}

export default function AccountSecurityPage() {
  const { user, policies, locale, loading: authLoading, refreshSessionData } = useAuth();

  const [enrollData, setEnrollData] = useState<EnrollPayload | null>(null);
  const [verifyCode, setVerifyCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [copiedSecret, setCopiedSecret] = useState(false);

  const [regenPassword, setRegenPassword] = useState("");
  const [regenCode, setRegenCode] = useState("");
  const [disablePassword, setDisablePassword] = useState("");
  const [disableCode, setDisableCode] = useState("");

  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const policyRequires2fa = Boolean(
    user && (policies?.require_2fa_roles || []).includes(user.role),
  );
  const enabled = Boolean(user?.totp_enabled);

  async function startEnrollment() {
    setBusy(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    setRecoveryCodes(null);
    try {
      const res = await apiFetch<EnrollPayload>("/api/v1/auth/2fa/enroll", {
        method: "POST",
        body: JSON.stringify({}),
      });
      setEnrollData(res);
      setVerifyCode("");
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Failed to start 2FA enrollment");
    } finally {
      setBusy(false);
    }
  }

  async function verifyEnrollment(e: React.FormEvent) {
    e.preventDefault();
    if (!enrollData || !verifyCode.trim()) {
      setErrorMsg("Enter the 6-digit code from your authenticator app.");
      return;
    }
    setBusy(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const res = await apiFetch<{ recovery_codes: string[] }>("/api/v1/auth/2fa/verify-enroll", {
        method: "POST",
        body: JSON.stringify({
          enroll_token: enrollData.enroll_token,
          code: verifyCode.trim(),
        }),
      });
      setEnrollData(null);
      setVerifyCode("");
      setRecoveryCodes(res.recovery_codes);
      setSuccessMsg("Two-factor authentication is now active. Save your recovery codes safely.");
      await refreshSessionData();
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Invalid verification code");
    } finally {
      setBusy(false);
    }
  }

  async function handleRegenerateCodes(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const res = await apiFetch<{ recovery_codes: string[] }>("/api/v1/auth/2fa/recovery-codes", {
        method: "POST",
        body: JSON.stringify({
          password: regenPassword,
          code: regenCode.trim(),
        }),
      });
      setRecoveryCodes(res.recovery_codes);
      setRegenPassword("");
      setRegenCode("");
      setSuccessMsg("Generated 8 new one-time recovery codes.");
      await refreshSessionData();
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Could not regenerate recovery codes");
    } finally {
      setBusy(false);
    }
  }

  async function handleDisable2fa(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await apiFetch("/api/v1/auth/2fa/disable", {
        method: "POST",
        body: JSON.stringify({
          password: disablePassword,
          code: disableCode.trim(),
        }),
      });
      setDisablePassword("");
      setDisableCode("");
      setRecoveryCodes(null);
      setSuccessMsg("Two-factor authentication has been disabled.");
      await refreshSessionData();
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Could not disable 2FA");
    } finally {
      setBusy(false);
    }
  }

  function downloadRecoveryCodes() {
    if (!recoveryCodes) return;
    const blob = new Blob([recoveryCodes.join("\n") + "\n"], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tablepulse-recovery-codes.txt";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-xl font-bold tracking-tight">
              {locale === "hi" ? "खाता सुरक्षा और 2FA" : "Account Security & Two-Factor Auth"}
            </h1>
            <p className="text-xs text-[var(--tp-label-secondary)]">
              {locale === "hi"
                ? "ऑथेंटिकेटर ऐप आधारित TOTP सुरक्षा और सिंगल-यूज़ रिकवरी कोड प्रबंधित करें"
                : "Manage TOTP authenticator app protection and single-use backup recovery codes"}
            </p>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${
              enabled
                ? "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200"
                : "bg-amber-100 text-amber-900 dark:bg-amber-950/60 dark:text-amber-200"
            }`}
          >
            {enabled ? (
              <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {enabled ? "2FA Enabled" : "2FA Not Enabled"}
          </span>
        </div>

        {policyRequires2fa && (
          <div
            role="status"
            className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs font-medium text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200"
          >
            Organization security policy requires 2FA for your role ({user?.role}).
          </div>
        )}

        {successMsg && (
          <div
            role="status"
            className="rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-xs font-semibold text-emerald-900 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200"
          >
            {successMsg}
          </div>
        )}
        {errorMsg && (
          <div
            role="alert"
            className="rounded-xl border border-red-300 bg-red-50 p-3 text-xs font-semibold text-red-900 dark:border-red-700 dark:bg-red-950/40 dark:text-red-200"
          >
            {errorMsg}
          </div>
        )}

        {!authLoading && user && !enabled && !enrollData && (
          <section className="tp-glass rounded-2xl border p-5 space-y-3">
            <h2 className="text-base font-bold flex items-center gap-2">
              <KeyRound className="h-4 w-4" aria-hidden="true" />
              Protect your sign-in with an Authenticator App
            </h2>
            <p className="text-xs text-[var(--tp-label-secondary)]">
              Scan a QR code with any standard TOTP app (Google Authenticator, 1Password, Aegis) and generate 8 one-time recovery codes.
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() => void startEnrollment()}
              className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-[var(--tp-accent)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-60"
            >
              {busy ? "Preparing QR..." : "Enable Two-Factor Authentication"}
            </button>
          </section>
        )}

        {enrollData && (
          <section className="tp-glass rounded-2xl border p-5 space-y-4">
            <h2 className="text-base font-bold">Scan QR Code & Confirm</h2>
            <div className="flex flex-col sm:flex-row items-center gap-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={enrollData.qr_svg_data_uri}
                alt="Authenticator TOTP QR code"
                className="h-44 w-44 rounded-xl bg-white p-2 border"
              />
              <div className="flex-1 space-y-2 w-full">
                <p className="text-xs text-[var(--tp-label-secondary)]">
                  Can&apos;t scan the QR image? Enter this Base32 key manually into your authenticator app:
                </p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 break-all rounded-lg bg-[var(--tp-inset-field)] px-3 py-2 font-mono text-xs border border-[var(--tp-card-border)] select-all">
                    {enrollData.secret}
                  </code>
                  <button
                    type="button"
                    onClick={() => {
                      void navigator.clipboard?.writeText(enrollData.secret);
                      setCopiedSecret(true);
                      setTimeout(() => setCopiedSecret(false), 1800);
                    }}
                    aria-label="Copy setup key"
                    className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl border border-[var(--tp-card-border)] px-3 text-xs font-semibold"
                  >
                    {copiedSecret ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </button>
                </div>
                <form onSubmit={verifyEnrollment} className="space-y-2 pt-2">
                  <label htmlFor="sec-verify-code" className="block text-xs font-semibold">
                    6-digit verification code
                  </label>
                  <input
                    id="sec-verify-code"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    value={verifyCode}
                    onChange={(e) => setVerifyCode(e.target.value)}
                    placeholder="123456"
                    className="w-full min-h-[44px] rounded-xl bg-[var(--tp-inset-field)] px-3 text-sm font-mono tracking-widest border border-[var(--tp-card-border)]"
                  />
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={busy}
                      className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-[var(--tp-accent)] px-4 text-xs font-semibold text-white disabled:opacity-60"
                    >
                      {busy ? "Verifying..." : "Verify & Activate"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setEnrollData(null)}
                      className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-[var(--tp-card-border)] px-4 text-xs font-semibold"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </section>
        )}

        {recoveryCodes && (
          <section className="tp-glass rounded-2xl border border-emerald-400/60 p-5 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-bold">One-Time Recovery Codes (Store Securely)</h2>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => void navigator.clipboard?.writeText(recoveryCodes.join("\n"))}
                  className="inline-flex min-h-[44px] items-center gap-1.5 rounded-xl border border-[var(--tp-card-border)] px-3 text-xs font-semibold"
                >
                  <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                  Copy All
                </button>
                <button
                  type="button"
                  onClick={downloadRecoveryCodes}
                  className="inline-flex min-h-[44px] items-center gap-1.5 rounded-xl border border-[var(--tp-card-border)] px-3 text-xs font-semibold"
                >
                  <Download className="h-3.5 w-3.5" aria-hidden="true" />
                  Download .txt
                </button>
              </div>
            </div>
            <ul className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs">
              {recoveryCodes.map((c) => (
                <li
                  key={c}
                  className="rounded-lg bg-[var(--tp-inset-field)] border border-[var(--tp-card-border)] py-2 text-center select-all"
                >
                  {c}
                </li>
              ))}
            </ul>
          </section>
        )}

        {enabled && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <section className="tp-glass rounded-2xl border p-4 space-y-3">
              <h2 className="text-sm font-bold">
                Regenerate Recovery Codes ({user?.recovery_codes_remaining ?? 0} remaining)
              </h2>
              <form onSubmit={handleRegenerateCodes} className="space-y-2.5 text-xs">
                <label className="block font-semibold">
                  Current Password
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={regenPassword}
                    onChange={(e) => setRegenPassword(e.target.value)}
                    required
                    className="mt-1 w-full min-h-[44px] rounded-xl bg-[var(--tp-inset-field)] px-3 text-sm border border-[var(--tp-card-border)]"
                  />
                </label>
                <label className="block font-semibold">
                  Current 6-digit TOTP Code
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    value={regenCode}
                    onChange={(e) => setRegenCode(e.target.value)}
                    required
                    className="mt-1 w-full min-h-[44px] rounded-xl bg-[var(--tp-inset-field)] px-3 text-sm font-mono border border-[var(--tp-card-border)]"
                  />
                </label>
                <button
                  type="submit"
                  disabled={busy}
                  className="inline-flex min-h-[44px] w-full items-center justify-center rounded-xl bg-[var(--tp-accent)] px-4 text-xs font-semibold text-white disabled:opacity-60"
                >
                  Regenerate 8 Recovery Codes
                </button>
              </form>
            </section>

            <section className="tp-glass rounded-2xl border border-red-400/40 p-4 space-y-3">
              <h2 className="text-sm font-bold">Disable Two-Factor Authentication</h2>
              <form onSubmit={handleDisable2fa} className="space-y-2.5 text-xs">
                <label className="block font-semibold">
                  Current Password
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={disablePassword}
                    onChange={(e) => setDisablePassword(e.target.value)}
                    required
                    disabled={policyRequires2fa}
                    className="mt-1 w-full min-h-[44px] rounded-xl bg-[var(--tp-inset-field)] px-3 text-sm border border-[var(--tp-card-border)] disabled:opacity-50"
                  />
                </label>
                <label className="block font-semibold">
                  Authenticator or Recovery Code
                  <input
                    type="text"
                    autoComplete="one-time-code"
                    value={disableCode}
                    onChange={(e) => setDisableCode(e.target.value)}
                    required
                    disabled={policyRequires2fa}
                    className="mt-1 w-full min-h-[44px] rounded-xl bg-[var(--tp-inset-field)] px-3 text-sm font-mono border border-[var(--tp-card-border)] disabled:opacity-50"
                  />
                </label>
                <button
                  type="submit"
                  disabled={busy || policyRequires2fa}
                  className="inline-flex min-h-[44px] w-full items-center justify-center rounded-xl bg-red-600 px-4 text-xs font-semibold text-white disabled:opacity-50"
                >
                  {policyRequires2fa ? "Required by Organization Policy" : "Disable 2FA"}
                </button>
              </form>
            </section>
          </div>
        )}
      </div>
    </AppShell>
  );
}
