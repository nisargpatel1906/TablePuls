"use client";

import React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { TableDetailDrawer } from "@/components/TableDetailDrawer";
import { useAuth } from "@/providers/AuthProvider";

export default function TableDetailPage() {
  const params = useParams<{ venueId: string; tableId: string }>();
  const { user, loading } = useAuth();
  const venueId = params?.venueId || "";
  const tableId = params?.tableId || "";

  if (!loading && !user) {
    return (
      <main className="mx-auto max-w-lg p-6 text-center">
        <h1 className="text-xl font-bold">Sign in required</h1>
        <Link
          href="/login"
          className="mt-4 inline-block rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-sm font-semibold text-white"
        >
          Go to Login
        </Link>
      </main>
    );
  }

  return (
    <AppShell venueId={venueId}>
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <div className="flex items-center justify-between">
          <Link
            href={`/venues/${venueId}/floor`}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--accent-primary)] hover:underline"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            Back to Live Floor Map
          </Link>
        </div>
        {!loading && user && venueId && tableId && (
          <TableDetailDrawer venueId={venueId} tableId={tableId} standalone />
        )}
      </div>
    </AppShell>
  );
}
