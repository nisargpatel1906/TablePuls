"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch, ApiError, type AuthUser } from "@/lib/api";
import { defaultHomeForRole } from "@/lib/rbac";
import { useAuth } from "@/providers/AuthProvider";

interface InviteInfo {
  email: string;
  role: string;
  organization_name: string;
  venue_ids: string[];
  expires_at: string;
}

function passwordScore(pw: string): { level: number; label: string } {
  let score = 0;
  if (pw.length >= 12) score += 1;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score += 1;
  if (/[0-9]/.test(pw)) score += 1;
  if (/[^A-Za-z0-9]/.test(pw) || pw.length >= 16) score += 1;
  const labels = ["Too short", "Weak", "Fair", "Good", "Strong"];
  return { level: score, label: labels[score] ?? "Weak" };
}

function RegisterInner() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token");
  const isBootstrap = params.get("bootstrap") === "true" || !token;
  const { setSession } = useAuth();

  const [inviteInfo, setInviteInfo] = useState<InviteInfo | null>(null);
  const [loadingInvite, setLoadingInvite] = useState(Boolean(token));
  const [tokenError, setTokenError] = useState<string | null>(null);

  const [orgName, setOrgName] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let active = true;
    (async () => {
      try {
        const info = await apiFetch<InviteInfo>(
          `/api/v1/auth/invite-info?token=${encodeURIComponent(token)}`,
          { skipAuth: true, retryOn401: false },
        );
        if (active) {
          setInviteInfo(info);
          setEmail(info.email);
        }
      } catch (err) {
        if (active) {
          setTokenError(
            err instanceof ApiError ? err.message : "Invitation link is invalid or expired.",
          );
        }
      } finally {
        if (active) setLoadingInvite(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [token]);

  const strength = passwordScore(password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (password.length < 12) {
      setErrorMsg("Password must be at least 12 characters long.");
      return;
    }
    if (password !== confirmPw) {
      setErrorMsg("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      if (token && !isBootstrap) {
        const res = await apiFetch<{ access_token: string; user: AuthUser }>(
          "/api/v1/auth/accept-invite",
          {
            method: "POST",
            skipAuth: true,
            body: JSON.stringify({ token, full_name: fullName.trim(), password }),
          },
        );
        await setSession(res.access_token, res.user);
        const me = await apiFetch<{ venues: Array<{ id: string }> }>("/api/v1/auth/me");
        router.push(defaultHomeForRole(res.user.role, me.venues[0]?.id));
      } else {
        const res = await apiFetch<{ access_token: string; user: AuthUser }>(
          "/api/v1/auth/bootstrap",
          {
            method: "POST",
            skipAuth: true,
            body: JSON.stringify({
              organization_name: orgName.trim(),
              email: email.trim(),
              full_name: fullName.trim(),
              password,
            }),
          },
        );
        await setSession(res.access_token, res.user);
        router.push("/onboarding");
      }
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (loadingInvite) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4">
        <div className="tp-card p-6 text-sm">Verifying invitation...</div>
      </main>
    );
  }

  if (tokenError) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4">
        <section className="w-full max-w-[460px] tp-card p-6 text-center space-y-4">
          <h1 className="text-xl font-bold">Invitation Expired or Invalid</h1>
          <p className="text-sm text-[var(--tp-label-secondary)]">{tokenError}</p>
          <Link
            href="/login"
            className="inline-flex min-h-[44px] items-center justify-center rounded-full bg-[var(--tp-accent)] px-6 text-sm font-semibold text-white"
          >
            Back to Sign In
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <section className="w-full max-w-[460px] tp-card p-6 sm:p-8">
        <div className="mb-5">
          <span className="inline-flex rounded-full bg-[#007AFF]/14 px-3 py-1 text-xs font-semibold text-[#0055B8] dark:text-[#64B5FF]">
            {token && inviteInfo ? "Invitation Verified" : "First-Run Setup"}
          </span>
          <h1 className="text-[22px] font-bold mt-2">
            {token && inviteInfo ? "Accept Invitation" : "Create Owner Account"}
          </h1>
          <p className="text-sm text-[var(--tp-label-secondary)] mt-1">
            {token && inviteInfo ? (
              <>
                Join <strong>{inviteInfo.organization_name}</strong> as{" "}
                <strong>{inviteInfo.role}</strong>.
              </>
            ) : (
              "Set up the initial TablePulse Owner account for your restaurant organization."
            )}
          </p>
        </div>

        {errorMsg && (
          <div
            role="alert"
            className="mb-4 rounded-2xl bg-[#FF3B30]/14 px-4 py-3 text-xs font-semibold text-[#B42318] dark:text-[#FF8A80]"
          >
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {!token && (
            <div>
              <label htmlFor="reg-org" className="block text-xs font-semibold mb-1.5">
                Organization / Restaurant Group Name
              </label>
              <input
                id="reg-org"
                required
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="Bistro Group"
                className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
              />
            </div>
          )}

          <div>
            <label htmlFor="reg-email" className="block text-xs font-semibold mb-1.5">
              {token ? "Invited Email" : "Owner Email"}
            </label>
            <input
              id="reg-email"
              type="email"
              required
              readOnly={Boolean(token)}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)] read-only:opacity-75"
            />
          </div>

          <div>
            <label htmlFor="reg-name" className="block text-xs font-semibold mb-1.5">
              Full Name
            </label>
            <input
              id="reg-name"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Enter Full Name"
              className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
            />
          </div>

          <div>
            <label htmlFor="reg-pw" className="block text-xs font-semibold mb-1.5">
              Password (min 12 characters)
            </label>
            <input
              id="reg-pw"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-describedby="pw-strength-desc"
              className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
            />
            <div className="mt-2 flex items-center gap-1.5">
              {[0, 1, 2, 3].map((idx) => (
                <div
                  key={idx}
                  className={`h-1.5 flex-1 rounded-full ${
                    idx < strength.level
                      ? strength.level >= 3
                        ? "bg-[#34C759]"
                        : "bg-[#FF9500]"
                      : "bg-[var(--tp-separator)]"
                  }`}
                />
              ))}
              <span
                id="pw-strength-desc"
                aria-live="polite"
                className="text-xs font-semibold text-[var(--tp-label-secondary)] ml-2"
              >
                {strength.label}
              </span>
            </div>
          </div>

          <div>
            <label htmlFor="reg-confirm" className="block text-xs font-semibold mb-1.5">
              Confirm Password
            </label>
            <input
              id="reg-confirm"
              type="password"
              required
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full min-h-[48px] rounded-full bg-[var(--tp-accent)] text-white text-sm font-semibold disabled:opacity-60"
          >
            {submitting ? "Creating Account..." : "Create Account"}
          </button>
        </form>

        <div className="mt-4 text-center">
          <Link href="/login" className="text-xs font-semibold text-[var(--tp-accent-text)] hover:underline">
            Already have an account? Sign In
          </Link>
        </div>
      </section>
    </main>
  );
}

export default function RegisterPage() {
  return (
    <React.Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center text-sm">Loading...</div>
      }
    >
      <RegisterInner />
    </React.Suspense>
  );
}
