export type TableState =
  | "FREE"
  | "OCCUPIED"
  | "NEEDS_SERVICE"
  | "NEEDS_CLEANING"
  | "RESERVED"
  | "UNKNOWN";

export interface TableStateMeta {
  state: TableState;
  label: string;
  borderClass: string;
  bgStyle: string;
  textStyle: string;
  accentHex: string;
  patternHint: string;
}

export const TABLE_STATE_META: Record<TableState, TableStateMeta> = {
  FREE: {
    state: "FREE",
    label: "Free",
    borderClass: "border-2 border-solid",
    bgStyle: "var(--state-free-bg)",
    textStyle: "var(--state-free-text)",
    accentHex: "#34C759",
    patternHint: "Solid outline",
  },
  OCCUPIED: {
    state: "OCCUPIED",
    label: "Occupied",
    borderClass: "border-2 border-solid",
    bgStyle: "var(--state-occupied-bg)",
    textStyle: "var(--state-occupied-text)",
    accentHex: "#FF3B30",
    patternHint: "Solid fill",
  },
  NEEDS_SERVICE: {
    state: "NEEDS_SERVICE",
    label: "Needs Service",
    borderClass: "border-2 border-solid tp-needs-service-ring",
    bgStyle: "var(--state-needs-service-bg)",
    textStyle: "var(--state-needs-service-text)",
    accentHex: "#FF9500",
    patternHint: "Pulsing ring",
  },
  NEEDS_CLEANING: {
    state: "NEEDS_CLEANING",
    label: "Needs Cleaning",
    borderClass: "border-2 border-dashed",
    bgStyle: "var(--state-needs-cleaning-bg)",
    textStyle: "var(--state-needs-cleaning-text)",
    accentHex: "#D97706",
    patternHint: "Dashed outline",
  },
  RESERVED: {
    state: "RESERVED",
    label: "Reserved",
    borderClass: "border-2 border-dotted",
    bgStyle: "var(--state-reserved-bg)",
    textStyle: "var(--state-reserved-text)",
    accentHex: "#007AFF",
    patternHint: "Dotted outline",
  },
  UNKNOWN: {
    state: "UNKNOWN",
    label: "Unsure / Offline",
    borderClass: "border-2 border-dashed tp-hatch-unknown",
    bgStyle: "var(--state-unknown-bg)",
    textStyle: "var(--state-unknown-text)",
    accentHex: "#8E8E93",
    patternHint: "Diagonal hatch",
  },
};

export function formatElapsed(isoTimestamp: string | null | undefined, nowMs: number): string {
  if (!isoTimestamp) return "00:00";
  const diffSec = Math.max(0, Math.floor((nowMs - new Date(isoTimestamp).getTime()) / 1000));
  const hrs = Math.floor(diffSec / 3600);
  const mins = Math.floor((diffSec % 3600) / 60);
  const secs = diffSec % 60;
  if (hrs > 0) {
    return `${String(hrs).padStart(2, "0")}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}
