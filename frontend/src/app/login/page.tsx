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
  const errorBannerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!loading && bootstrapRequired) {
      router.replace("/register?bootstrap=true");
    } else if (!loading && user) {
      router.replace(defaultHomeForRole(user.role, venues[0]?.id));
    }
  }, [loading, bootstrapRequired, user, venues, router]);

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
      const res = await apiFetch<{ access_token: string; user: AuthUser }>(
        "/api/v1/auth/login",
        {
          method: "POST",
          skipAuth: true,
          retryOn401: false,
          body: JSON.stringify({ email: email.trim(), password }),
        },
      );
      await setSession(res.access_token, res.user);
      const me = await apiFetch<{ venues: Array<{ id: string }> }>("/api/v1/auth/me");
      router.push(defaultHomeForRole(res.user.role, me.venues[0]?.id));
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

        {demoMode && (
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
