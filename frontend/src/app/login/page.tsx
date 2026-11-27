"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Grid2x2 } from "lucide-react";
import { apiFetch, ApiError, type AuthUser } from "@/lib/api";
import { defaultHomeForRole } from "@/lib/rbac";
import { useAuth } from "@/providers/AuthProvider";

function LoginFormInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reasonExpired = searchParams.get("reason") === "expired";
  const { setSession, demoMode, bootstrapRequired, user, venues, loading } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [retryCountdown, setRetryCountdown] = useState<number>(0);

  // Two-step 2FA state
  const [twoFaChallenge, setTwoFaChallenge] = useState<string | null>(null);
  const [twoFaCode, setTwoFaCode] = useState("");
  const [setupChallenge, setSetupChallenge] = useState<string | null>(null);
  const [enrollData, setEnrollData] = useState<{
    enroll_token: string;
    secret: string;
    qr_svg_data_uri: string;
  } | null>(null);
  const [setupVerifyCode, setSetupVerifyCode] = useState("");
  const [issuedRecoveryCodes, setIssuedRecoveryCodes] = useState<string[] | null>(null);
  const [pendingSession, setPendingSession] = useState<{
    access_token: string;
    user: AuthUser;
  } | null>(null);
  const errorBannerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (submitting) return;
    if (!loading && bootstrapRequired) {
      router.replace("/register?bootstrap=true");
    } else if (!loading && user) {
      router.replace(defaultHomeForRole(user.role, venues[0]?.id));
    }
  }, [loading, submitting, bootstrapRequired, user, venues, router]);

  useEffect(() => {
    if (retryCountdown <= 0) return;
    const id = setInterval(() => {
      setRetryCountdown((s) => Math.max(0, s - 1));
    }, 1000);
    return () => clearInterval(id);
  }, [retryCountdown]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!email.trim() || !email.includes("@")) {
      errs.email = "Enter a valid email";
    }
    if (!password) {
      errs.password = "Password is required";
    }
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      setErrorMsg("Please correct the highlighted fields.");
      return;
    }

    setFieldErrors({});
    setErrorMsg(null);
    setSubmitting(true);
    try {
      const res = await apiFetch<{
        access_token?: string;
        user?: AuthUser;
        requires_2fa?: boolean;
        requires_2fa_setup?: boolean;
        challenge_token?: string;
      }>("/api/v1/auth/login", {
        method: "POST",
        skipAuth: true,
        retryOn401: false,
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (res.requires_2fa && res.challenge_token) {
        setTwoFaChallenge(res.challenge_token);
        setTwoFaCode("");
        return;
      }

      if (res.requires_2fa_setup && res.challenge_token) {
        setSetupChallenge(res.challenge_token);
        const enr = await apiFetch<{
          enroll_token: string;
          secret: string;
          qr_svg_data_uri: string;
        }>("/api/v1/auth/2fa/enroll", {
          method: "POST",
          skipAuth: true,
          retryOn401: false,
          body: JSON.stringify({ challenge_token: res.challenge_token }),
        });
        setEnrollData(enr);
        setSetupVerifyCode("");
        return;
      }

      if (res.access_token && res.user) {
        const loadedVenues = await setSession(res.access_token, res.user);
        router.push(defaultHomeForRole(res.user.role, loadedVenues[0]?.id));
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          setRetryCountdown(60);
          setErrorMsg("Too many login attempts. Please wait before trying again.");
        } else {
          setErrorMsg(err.message || "Invalid email or password");
        }
        if (err.fields) setFieldErrors(err.fields);
      } else {
        setErrorMsg("Unable to reach server. Please try again.");
      }
      setTimeout(() => errorBannerRef.current?.focus(), 0);
    } finally {
      setSubmitting(false);
    }
  };

  const handleTwoFaVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!twoFaChallenge || !twoFaCode.trim()) {
      setErrorMsg("Enter your 6-digit authenticator code or recovery code.");
      return;
    }
    setErrorMsg(null);
    setSubmitting(true);
    try {
      const res = await apiFetch<{ access_token: string; user: AuthUser }>(
        "/api/v1/auth/2fa/verify",
        {
          method: "POST",
          skipAuth: true,
          retryOn401: false,
          body: JSON.stringify({
            challenge_token: twoFaChallenge,
            code: twoFaCode.trim(),
          }),
        },
      );
      await setSession(res.access_token, res.user);
      const me = await apiFetch<{ venues: Array<{ id: string }> }>("/api/v1/auth/me");
      router.push(defaultHomeForRole(res.user.role, me.venues[0]?.id));
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          setRetryCountdown(60);
          setErrorMsg("Too many verification attempts. Please wait or restart sign-in.");
        } else {
          setErrorMsg(err.message || "Invalid verification or recovery code");
        }
      } else {
        setErrorMsg("Unable to reach server. Please try again.");
      }
      setTimeout(() => errorBannerRef.current?.focus(), 0);
    } finally {
      setSubmitting(false);
    }
  };

  const handleEnforcedEnrollVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!setupChallenge || !enrollData || !setupVerifyCode.trim()) {
      setErrorMsg("Enter the 6-digit code from your authenticator app.");
      return;
    }
    setErrorMsg(null);
    setSubmitting(true);
    try {
      const res = await apiFetch<{
        access_token: string;
        user: AuthUser;
        recovery_codes: string[];
      }>("/api/v1/auth/2fa/verify-enroll", {
        method: "POST",
        skipAuth: true,
        retryOn401: false,
        body: JSON.stringify({
          challenge_token: setupChallenge,
          enroll_token: enrollData.enroll_token,
          code: setupVerifyCode.trim(),
        }),
      });
      setIssuedRecoveryCodes(res.recovery_codes);
      setPendingSession({ access_token: res.access_token, user: res.user });
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Invalid 6-digit code");
      setTimeout(() => errorBannerRef.current?.focus(), 0);
    } finally {
      setSubmitting(false);
    }
  };

  const finishEnforcedSetup = async () => {
    if (!pendingSession) return;
    await setSession(pendingSession.access_token, pendingSession.user);
    const me = await apiFetch<{ venues: Array<{ id: string }> }>("/api/v1/auth/me");
    router.push(defaultHomeForRole(pendingSession.user.role, me.venues[0]?.id));
  };

  const handleDemoLogin = async () => {
    setDemoLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiFetch<{ access_token: string; user: AuthUser }>(
        "/api/v1/auth/demo-login",
        {
          method: "POST",
          skipAuth: true,
          retryOn401: false,
        },
      );
      await setSession(res.access_token, res.user);
      const me = await apiFetch<{ venues: Array<{ id: string }> }>("/api/v1/auth/me");
      router.push(defaultHomeForRole(res.user.role, me.venues[0]?.id));
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Demo login failed");
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <section className="w-full max-w-[430px] tp-card p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col items-center text-center mb-6">
          <div className="h-12 w-12 rounded-2xl bg-[var(--tp-label-primary)] text-[var(--tp-surface)] flex items-center justify-center mb-3">
            <Grid2x2 className="h-6 w-6" aria-hidden="true" />
          </div>
          <h1 className="text-[22px] font-bold tracking-tight">Sign in to TablePulse</h1>
          <p className="text-sm text-[var(--tp-label-secondary)] mt-1">
            Live floor intelligence &amp; table turnover operations
          </p>
        </div>

        {reasonExpired && (
          <div
            role="status"
            className="mb-4 rounded-2xl bg-[#FF9500]/15 px-4 py-3 text-xs font-medium text-[#9A4E00] dark:text-[#FFB340]"
          >
            Your session expired. Please sign in again.
          </div>
        )}

        {errorMsg && (
          <div
            ref={errorBannerRef}
            tabIndex={-1}
            role="alert"
            className="mb-4 rounded-2xl bg-[#FF3B30]/14 px-4 py-3 text-xs font-semibold text-[#B42318] dark:text-[#FF8A80]"
          >
            {errorMsg}
            {retryCountdown > 0 ? ` (${retryCountdown}s)` : ""}
          </div>
        )}

        {issuedRecoveryCodes && pendingSession ? (
          <div className="space-y-4">
            <div
              role="status"
              className="rounded-2xl bg-[#34C759]/15 px-4 py-3 text-xs font-semibold text-[#1E6B34] dark:text-[#7CE89B]"
            >
              Two-factor authentication is now enabled. Save these 8 single-use recovery codes before continuing.
            </div>
            <ul className="grid grid-cols-2 gap-2 rounded-2xl bg-[var(--tp-inset-field)] p-3 font-mono text-xs border border-[var(--tp-card-border)]">
              {issuedRecoveryCodes.map((c) => (
                <li key={c} className="text-center py-1 rounded bg-[var(--tp-surface)]">
                  {c}
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={() => void finishEnforcedSetup()}
              className="w-full min-h-[48px] rounded-full bg-[var(--tp-accent)] text-white text-sm font-semibold"
            >
              Continue to TablePulse
            </button>
          </div>
        ) : setupChallenge && enrollData ? (
          <form onSubmit={handleEnforcedEnrollVerify} noValidate className="space-y-4">
            <div
              role="status"
              className="rounded-2xl bg-[#FF9500]/15 px-4 py-3 text-xs font-medium text-[#9A4E00] dark:text-[#FFB340]"
            >
              Your organization requires two-factor authentication for your role. Scan the QR code or copy the key below.
            </div>
            <div className="flex flex-col items-center gap-3 rounded-2xl bg-[var(--tp-inset-field)] p-4 border border-[var(--tp-card-border)]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={enrollData.qr_svg_data_uri}
                alt="Two-factor authenticator setup QR code"
                className="h-44 w-44 rounded-xl bg-white p-2"
              />
              <div className="w-full text-center">
                <span className="block text-[11px] font-semibold text-[var(--tp-label-secondary)]">
                  Manual setup key
                </span>
                <code className="mt-1 block break-all rounded-lg bg-[var(--tp-surface)] px-2.5 py-1.5 font-mono text-xs select-all">
                  {enrollData.secret}
                </code>
              </div>
            </div>
            <div>
              <label htmlFor="setup-totp-code" className="block text-xs font-semibold mb-1.5">
                6-digit verification code
              </label>
              <input
                id="setup-totp-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={setupVerifyCode}
                onChange={(e) => setSetupVerifyCode(e.target.value)}
                placeholder="123456"
                className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm font-mono tracking-widest border border-[var(--tp-card-border)]"
              />
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="w-full min-h-[48px] rounded-full bg-[var(--tp-accent)] text-white text-sm font-semibold disabled:opacity-60"
            >
              {submitting ? "Activating 2FA..." : "Verify & Activate 2FA"}
            </button>
            <button
              type="button"
              onClick={() => {
                setSetupChallenge(null);
                setEnrollData(null);
                setErrorMsg(null);
              }}
              className="w-full min-h-[44px] rounded-full border border-[var(--tp-card-border)] text-xs font-semibold"
            >
              Back to password sign-in
            </button>
          </form>
        ) : twoFaChallenge ? (
          <form onSubmit={handleTwoFaVerify} noValidate className="space-y-4">
            <div
              role="status"
              className="rounded-2xl bg-[var(--tp-inset-field)] px-4 py-3 text-xs font-medium text-[var(--tp-label-secondary)] border border-[var(--tp-card-border)]"
            >
              Enter the 6-digit code from your authenticator app or an 8-character single-use recovery code.
            </div>
            <div>
              <label htmlFor="login-2fa-code" className="block text-xs font-semibold mb-1.5">
                Authenticator or recovery code
              </label>
              <input
                id="login-2fa-code"
                type="text"
                autoComplete="one-time-code"
                value={twoFaCode}
                onChange={(e) => setTwoFaCode(e.target.value)}
                placeholder="123456 or ABCD-EFGH"
                className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm font-mono tracking-wider border border-[var(--tp-card-border)]"
              />
            </div>
            <button
              type="submit"
              disabled={submitting || retryCountdown > 0}
              className="w-full min-h-[48px] rounded-full bg-[var(--tp-accent)] text-white text-sm font-semibold disabled:opacity-60"
            >
              {submitting ? "Verifying..." : "Verify & Sign In"}
            </button>
            <button
              type="button"
              onClick={() => {
                setTwoFaChallenge(null);
                setTwoFaCode("");
                setErrorMsg(null);
              }}
              className="w-full min-h-[44px] rounded-full border border-[var(--tp-card-border)] text-xs font-semibold"
            >
              Back to password sign-in
            </button>
          </form>
        ) : (
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <div>
            <label htmlFor="login-email" className="block text-xs font-semibold mb-1.5">
              Email address
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={Boolean(fieldErrors.email)}
              aria-describedby={fieldErrors.email ? "login-email-err" : undefined}
              placeholder="manager@restaurant.com"
              className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
            />
            {fieldErrors.email && (
              <p id="login-email-err" className="mt-1 text-xs text-[#B42318] dark:text-[#FF8A80]">
                {fieldErrors.email}
              </p>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label htmlFor="login-password" className="block text-xs font-semibold">
                Password
              </label>
              <Link
                href="/reset-password"
                className="text-xs font-semibold text-[var(--tp-accent-text)] hover:underline min-h-[44px] inline-flex items-center"
              >
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={Boolean(fieldErrors.password)}
                aria-describedby={fieldErrors.password ? "login-pw-err" : undefined}
                placeholder="Enter your password"
                className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] pl-3.5 pr-12 text-sm border border-[var(--tp-card-border)]"
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                className="absolute right-1 top-1/2 -translate-y-1/2 h-11 w-11 inline-flex items-center justify-center rounded-xl text-[var(--tp-label-secondary)]"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Eye className="h-4 w-4" aria-hidden="true" />
                )}
              </button>
            </div>
            {fieldErrors.password && (
              <p id="login-pw-err" className="mt-1 text-xs text-[#B42318] dark:text-[#FF8A80]">
                {fieldErrors.password}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={submitting || retryCountdown > 0}
            className="w-full min-h-[48px] rounded-full bg-[var(--tp-accent)] text-white text-sm font-semibold disabled:opacity-60 transition active:scale-[0.98]"
          >
            {submitting ? "Signing in..." : "Sign In"}
          </button>
        </form>
        )}

        {demoMode && !twoFaChallenge && !setupChallenge && (
          <div className="mt-5 rounded-[18px] bg-[var(--tp-inset-field)] p-4 border border-[var(--tp-card-border)]">
            <div className="text-xs font-semibold text-[var(--tp-label-secondary)] mb-2">
              Demo Mode Enabled (DEMO_MODE=true)
            </div>
            <button
              type="button"
              disabled={demoLoading}
              onClick={handleDemoLogin}
              className="w-full min-h-[44px] rounded-full bg-[var(--tp-surface)] border border-[var(--tp-card-border)] text-sm font-semibold hover:opacity-90 disabled:opacity-60"
            >
              {demoLoading ? "Starting Demo..." : "Sign in as Demo Manager"}
            </button>
          </div>
        )}
      </section>
    </main>
  );
}

export default function LoginPage() {
  return (
    <React.Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center text-sm">Loading...</div>
      }
    >
      <LoginFormInner />
    </React.Suspense>
  );
}
