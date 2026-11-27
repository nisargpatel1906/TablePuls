"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Download, Lock, Plus, RefreshCw, ShieldAlert } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, ApiError } from "@/lib/api";
import { hasCapability, type Role } from "@/lib/rbac";
import { useAuth } from "@/providers/AuthProvider";

interface OrgUserDTO {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  assigned_venue_ids: string[];
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

interface AuditLogDTO {
  id: string;
  action: string;
  target_type: string;
  target_id: string | null;
  actor_user_id: string | null;
  ip_address: string | null;
  created_at: string;
}

export default function UsersAndAuditPage() {
  const { user, venues, loading: authLoading } = useAuth();
  const canManageUsers = hasCapability(user?.role, "users.manage_standard");
  const canViewAudit = hasCapability(user?.role, "audit_logs.view");
  const canPrivileged = hasCapability(user?.role, "users.manage_privileged");

  const [tab, setTab] = useState<"members" | "audit">("members");
  const [members, setMembers] = useState<OrgUserDTO[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [generatedUrl, setGeneratedUrl] = useState<string | null>(null);

  const [showInvite, setShowInvite] = useState(false);
  const [invEmail, setInvEmail] = useState("");
  const [invRole, setInvRole] = useState<Role>("HOST");
  const [invVenueId, setInvVenueId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!invVenueId && venues[0]?.id) {
      setInvVenueId(venues[0].id);
    }
  }, [venues, invVenueId]);

  const loadData = useCallback(async () => {
    if (!canManageUsers) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const usersRes = await apiFetch<{ items: OrgUserDTO[] }>("/api/v1/org/users?page_size=50");
      setMembers(usersRes.items);
      if (canViewAudit) {
        const auditRes = await apiFetch<{ items: AuditLogDTO[] }>(
          "/api/v1/org/audit-logs?page_size=50",
        );
        setAuditLogs(auditRes.items);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load org directory");
    } finally {
      setLoading(false);
    }
  }, [canManageUsers, canViewAudit]);

  useEffect(() => {
    if (!authLoading && user) {
      void loadData();
    }
  }, [authLoading, user, loadData]);

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    setGeneratedUrl(null);
    try {
      const res = await apiFetch<{ invite_url: string | null; email_sent?: boolean; email: string }>(
        "/api/v1/org/users/invite",
        {
          method: "POST",
          body: JSON.stringify({
            email: invEmail.trim(),
            role: invRole,
            venue_ids: invVenueId ? [invVenueId] : [],
          }),
        },
      );
      setSuccessMsg(
        res.email_sent && !res.invite_url
          ? `Sent 48h invitation email to ${res.email}.`
          : `Created 48h invite link for ${res.email}.`,
      );
      setGeneratedUrl(res.invite_url ?? null);
      setInvEmail("");
      setShowInvite(false);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to invite user");
    } finally {
      setSubmitting(false);
    }
  }

  async function changeRole(targetId: string, newRole: Role) {
    setError(null);
    setSuccessMsg(null);
    try {
      await apiFetch(`/api/v1/org/users/${targetId}`, {
        method: "PATCH",
        body: JSON.stringify({ role: newRole }),
      });
      setSuccessMsg(`Updated role to ${newRole}.`);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update role");
    }
  }

  async function revokeSessions(targetId: string) {
    setError(null);
    setSuccessMsg(null);
    try {
      await apiFetch(`/api/v1/org/users/${targetId}/revoke-sessions`, {
        method: "POST",
      });
      setSuccessMsg("Revoked active sessions cleanly.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to revoke sessions");
    }
  }

  async function generateResetLink(targetId: string) {
    setError(null);
    setGeneratedUrl(null);
    try {
      const res = await apiFetch<{ reset_url: string }>(
        `/api/v1/org/users/${targetId}/reset-link`,
        { method: "POST" },
      );
      setGeneratedUrl(res.reset_url);
      setSuccessMsg("Generated single-use 30-min reset link.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create reset link");
    }
  }

  async function exportAuditCsv() {
    try {
      const blob = await apiFetch<Blob>("/api/v1/org/audit-logs?format=csv");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "tablepulse-audit-logs.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "CSV export failed");
    }
  }

  return (
    <AppShell>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Users, Roles & Audit Log</h1>
            <p className="text-xs text-[var(--text-secondary)]">
              Role-scoped team access, invite links, session revocation, and immutable audit trail
            </p>
          </div>
          {canManageUsers && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void loadData()}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] p-2"
                aria-label="Refresh users"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => setShowInvite((v) => !v)}
                className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Invite User
              </button>
            </div>
          )}
        </div>

        {!authLoading && user && !canManageUsers && (
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
        {generatedUrl && (
          <div className="tp-glass flex flex-col gap-1 rounded-xl border p-3 text-xs">
            <span className="font-bold">Single-Use Setup / Reset URL (Copy & Share):</span>
            <code className="break-all rounded bg-[var(--surface-solid)] p-2 font-mono">
              {generatedUrl}
            </code>
          </div>
        )}
        {error && (
          <div role="alert" className="flex items-center gap-2 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800">
            <ShieldAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {canManageUsers && showInvite && (
          <form
            onSubmit={handleInvite}
            className="tp-glass grid grid-cols-1 gap-3 rounded-xl border p-4 md:grid-cols-4"
          >
            <label className="flex flex-col gap-1 text-xs font-medium">
              Venue Scope
              <select
                value={invVenueId}
                onChange={(e) => setInvVenueId(e.target.value)}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-2 text-sm"
              >
                {venues.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Email *
              <input
                type="email"
                required
                value={invEmail}
                onChange={(e) => setInvEmail(e.target.value)}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-2 text-sm"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Role
              <select
                value={invRole}
                onChange={(e) => setInvRole(e.target.value as Role)}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2.5 py-2 text-sm"
              >
                {canPrivileged && <option value="OWNER">OWNER</option>}
                {canPrivileged && <option value="MANAGER">MANAGER</option>}
                <option value="HOST">HOST</option>
                <option value="STAFF">STAFF</option>
                <option value="VIEWER">VIEWER</option>
              </select>
            </label>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={submitting}
                className="min-h-[40px] w-full rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white"
              >
                {submitting ? "Creating..." : "Create Invite Link"}
              </button>
            </div>
          </form>
        )}

        {canManageUsers && (
          <div className="flex items-center justify-between gap-2">
            <div className="flex gap-2" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={tab === "members"}
                onClick={() => setTab("members")}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold ${
                  tab === "members"
                    ? "bg-[var(--accent-primary)] text-white"
                    : "border border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                }`}
              >
                Team Members ({members.length})
              </button>
              {canViewAudit && (
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === "audit"}
                  onClick={() => setTab("audit")}
                  className={`rounded-full px-3 py-1.5 text-xs font-semibold ${
                    tab === "audit"
                      ? "bg-[var(--accent-primary)] text-white"
                      : "border border-[var(--border-subtle)] bg-[var(--surface-solid)]"
                  }`}
                >
                  Audit Log ({auditLogs.length})
                </button>
              )}
            </div>

            {tab === "audit" && canViewAudit && (
              <button
                type="button"
                onClick={() => void exportAuditCsv()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-3 py-1.5 text-xs font-semibold"
              >
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
                Export Audit CSV
              </button>
            )}
          </div>
        )}

        {canManageUsers && loading && (
          <div className="tp-glass rounded-xl border p-8 text-center text-sm text-[var(--text-secondary)]">
            Loading directory...
          </div>
        )}

        {canManageUsers && !loading && tab === "members" && (
          <>
            <div className="space-y-3 md:hidden">
              {members.map((m) => (
                <div key={m.id} className="tp-glass rounded-xl border p-3.5 text-xs">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-sm">{m.full_name}</p>
                      <p className="truncate font-mono text-[11px] text-[var(--text-secondary)]">{m.email}</p>
                    </div>
                    <span
                      className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold ${
                        m.is_active
                          ? "bg-emerald-500/15 text-emerald-700"
                          : "bg-slate-500/15 text-slate-600"
                      }`}
                    >
                      {m.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border-subtle)] pt-2.5">
                    {canPrivileged ? (
                      <select
                        aria-label={`Mobile role for ${m.full_name}`}
                        value={m.role}
                        onChange={(e) => void changeRole(m.id, e.target.value as Role)}
                        className="rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2 py-1 text-xs font-semibold"
                      >
                        <option value="OWNER">OWNER</option>
                        <option value="MANAGER">MANAGER</option>
                        <option value="HOST">HOST</option>
                        <option value="STAFF">STAFF</option>
                        <option value="VIEWER">VIEWER</option>
                      </select>
                    ) : (
                      <span className="rounded bg-[var(--surface-solid)] px-2 py-1 font-semibold">
                        {m.role}
                      </span>
                    )}
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => void revokeSessions(m.id)}
                        className="rounded px-2.5 py-1 font-semibold text-red-600 hover:bg-red-50"
                      >
                        Revoke
                      </button>
                      {canPrivileged && (
                        <button
                          type="button"
                          onClick={() => void generateResetLink(m.id)}
                          className="rounded border border-[var(--border-subtle)] px-2.5 py-1 font-semibold"
                        >
                          Reset Link
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="tp-glass hidden overflow-x-auto rounded-xl border md:block">
              <table className="w-full min-w-[640px] text-left text-xs">
                <thead className="border-b border-[var(--border-subtle)] bg-[var(--surface-solid)] uppercase text-[var(--text-secondary)]">
                  <tr>
                    <th scope="col" className="px-4 py-3">Name</th>
                    <th scope="col" className="px-4 py-3">Email</th>
                    <th scope="col" className="px-4 py-3">Role</th>
                    <th scope="col" className="px-4 py-3">Status</th>
                    <th scope="col" className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  {members.map((m) => (
                    <tr key={m.id}>
                      <td className="px-4 py-3 font-semibold">{m.full_name}</td>
                      <td className="px-4 py-3 font-mono">{m.email}</td>
                      <td className="px-4 py-3">
                        {canPrivileged ? (
                          <select
                            aria-label={`Role for ${m.full_name}`}
                            value={m.role}
                            onChange={(e) => void changeRole(m.id, e.target.value as Role)}
                            className="rounded border border-[var(--border-subtle)] bg-[var(--surface-solid)] px-2 py-1 text-xs font-semibold"
                          >
                            <option value="OWNER">OWNER</option>
                            <option value="MANAGER">MANAGER</option>
                            <option value="HOST">HOST</option>
                            <option value="STAFF">STAFF</option>
                            <option value="VIEWER">VIEWER</option>
                          </select>
                        ) : (
                          <span className="rounded bg-[var(--surface-solid)] px-2 py-1 font-semibold">
                            {m.role}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${
                            m.is_active
                              ? "bg-emerald-500/15 text-emerald-700"
                              : "bg-slate-500/15 text-slate-600"
                          }`}
                        >
                          {m.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => void revokeSessions(m.id)}
                            className="rounded px-2 py-1 font-semibold text-red-600 hover:bg-red-50"
                          >
                            Revoke
                          </button>
                          {canPrivileged && (
                            <button
                              type="button"
                              onClick={() => void generateResetLink(m.id)}
                              className="rounded border border-[var(--border-subtle)] px-2 py-1 font-semibold"
                            >
                              Reset Link
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {canManageUsers && !loading && tab === "audit" && canViewAudit && (
          <div className="tp-glass overflow-x-auto rounded-xl border">
            <table className="w-full min-w-[640px] text-left text-xs">
              <thead className="border-b border-[var(--border-subtle)] bg-[var(--surface-solid)] uppercase text-[var(--text-secondary)]">
                <tr>
                  <th scope="col" className="px-4 py-3">Timestamp</th>
                  <th scope="col" className="px-4 py-3">Action</th>
                  <th scope="col" className="px-4 py-3">Target</th>
                  <th scope="col" className="px-4 py-3">IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {auditLogs.map((a) => (
                  <tr key={a.id}>
                    <td className="px-4 py-3 font-mono">
                      {new Date(a.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 font-bold">{a.action}</td>
                    <td className="px-4 py-3 font-mono">
                      {a.target_type} {a.target_id ? a.target_id.slice(0, 8) : ""}
                    </td>
                    <td className="px-4 py-3 font-mono">{a.ip_address || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}
