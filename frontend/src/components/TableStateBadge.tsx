"use client";

import React from "react";
import {
  Bell,
  Bookmark,
  CheckCircle2,
  HelpCircle,
  Sparkles,
  Users,
} from "lucide-react";
import { TABLE_STATE_META, type TableState } from "@/lib/table-states";

export function TableStateIcon({
  state,
  className = "h-4 w-4",
}: {
  state: TableState;
  className?: string;
}) {
  switch (state) {
    case "FREE":
      return <CheckCircle2 className={className} aria-hidden="true" />;
    case "OCCUPIED":
      return <Users className={className} aria-hidden="true" />;
    case "NEEDS_SERVICE":
      return <Bell className={className} aria-hidden="true" />;
    case "NEEDS_CLEANING":
      return <Sparkles className={className} aria-hidden="true" />;
    case "RESERVED":
      return <Bookmark className={className} aria-hidden="true" />;
    case "UNKNOWN":
    default:
      return <HelpCircle className={className} aria-hidden="true" />;
  }
}

export function TableStateBadge({
  state,
  compact = false,
}: {
  state: TableState;
  compact?: boolean;
}) {
  const meta = TABLE_STATE_META[state] ?? TABLE_STATE_META.UNKNOWN;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${meta.borderClass}`}
      style={{
        backgroundColor: meta.bgStyle,
        color: meta.textStyle,
        borderColor: meta.accentHex,
      }}
    >
      <TableStateIcon state={state} className="h-3.5 w-3.5 shrink-0" />
      {!compact && <span>{meta.label}</span>}
    </span>
  );
}
