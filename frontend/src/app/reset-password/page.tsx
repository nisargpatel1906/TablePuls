"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";

function ResetPasswordInner() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token");

  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);
    if (!email.includes("@")) {
      setErrorMsg("Enter a valid email address.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await apiFetch<{ message: string }>("/api/v1/auth/forgot-password", {
        method: "POST",
        skipAuth: true,
        body: JSON.stringify({ email: email.trim() }),
      });
      setSuccessMsg(res.message);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Request failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (newPassword.length < 12) {
      setErrorMsg("Password must be at least 12 characters long.");
      return;
    }
    if (newPassword !== confirmPw) {
      setErrorMsg("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await apiFetch("/api/v1/auth/reset-password", {
        method: "POST",
        skipAuth: true,
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      setSuccessMsg("Password updated! Redirecting to Sign In...");
      setTimeout(() => router.push("/login"), 1200);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Reset failed or token expired.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <section className="w-full max-w-[430px] tp-card p-6 sm:p-8">
        <h1 className="text-[21px] font-bold mb-1">
          {token ? "Set New Password" : "Reset Password"}
        </h1>
        <p className="text-sm text-[var(--tp-label-secondary)] mb-5">
          {token
            ? "Choose a strong password of at least 12 characters."
            : "Enter your account email to request a 30-minute single-use reset link."}
        </p>

        {errorMsg && (
          <div
            role="alert"
            className="mb-4 rounded-2xl bg-[#FF3B30]/14 px-4 py-3 text-xs font-semibold text-[#B42318] dark:text-[#FF8A80]"
          >
            {errorMsg}
          </div>
        )}
        {successMsg && (
          <div
            role="status"
            className="mb-4 rounded-2xl bg-[#34C759]/14 px-4 py-3 text-xs font-semibold text-[#146C2E] dark:text-[#6EE787]"
          >
            {successMsg}
          </div>
        )}

        {!token ? (
          <form onSubmit={handleRequest} className="space-y-4">
            <div>
              <label htmlFor="reset-email" className="block text-xs font-semibold mb-1.5">
                Email address
              </label>
              <input
                id="reset-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@restaurant.com"
                className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
              />
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="w-full min-h-[48px] rounded-full bg-[var(--tp-accent)] text-white text-sm font-semibold disabled:opacity-60"
            >
              {submitting ? "Sending..." : "Send Reset Link"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleConfirm} className="space-y-4">
            <div>
              <label htmlFor="new-pw" className="block text-xs font-semibold mb-1.5">
                New Password (min 12 chars)
              </label>
              <input
                id="new-pw"
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full min-h-[46px] rounded-[14px] bg-[var(--tp-inset-field)] px-3.5 text-sm border border-[var(--tp-card-border)]"
              />
            </div>
            <div>
              <label htmlFor="confirm-new-pw" className="block text-xs font-semibold mb-1.5">
                Confirm New Password
              </label>
              <input
                id="confirm-new-pw"
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
              {submitting ? "Resetting..." : "Reset Password"}
            </button>
          </form>
        )}

        <div className="mt-5 text-center">
          <Link
            href="/login"
            className="inline-flex min-h-[44px] items-center text-xs font-semibold text-[var(--tp-accent-text)] hover:underline"
          >
            Back to Sign In
          </Link>
        </div>
      </section>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <React.Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center text-sm">Loading...</div>
      }
    >
      <ResetPasswordInner />
    </React.Suspense>
  );
}
