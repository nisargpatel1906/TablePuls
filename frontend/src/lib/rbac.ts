export type Role = "OWNER" | "MANAGER" | "HOST" | "STAFF" | "VIEWER";

export type Capability =
  | "floor.view"
  | "cameras.live.view"
  | "tables.mark_clean_or_served"
  | "tables.override_full"
  | "tables.flag_ai"
  | "alerts.view"
  | "alerts.resolve"
  | "waitlist.manage"
  | "turnover.view"
  | "analytics.view_export"
  | "ml_review.label"
  | "ml_review.export"
  | "venues.manage"
  | "cameras.manage"
  | "polygons.calibrate"
  | "alert_rules.manage"
  | "users.manage_standard"
  | "users.manage_privileged"
  | "audit_logs.view"
  | "system.manage"
  | "privacy.purge"
  | "tables.read"
  | "tables.manage"
  | "menu.read"
  | "menu.manage"
  | "menu.availability"
  | "menu.currency_manage"
  | "qr.read"
  | "qr.manage";

const CAPABILITY_ROLES: Record<Capability, Role[]> = {
  "floor.view": ["OWNER", "MANAGER", "HOST", "STAFF", "VIEWER"],
  "cameras.live.view": ["OWNER", "MANAGER"],
  "tables.mark_clean_or_served": ["OWNER", "MANAGER", "HOST", "STAFF"],
  "tables.override_full": ["OWNER", "MANAGER", "HOST"],
  "tables.flag_ai": ["OWNER", "MANAGER", "HOST", "STAFF"],
  "alerts.view": ["OWNER", "MANAGER", "HOST", "STAFF"],
  "alerts.resolve": ["OWNER", "MANAGER", "HOST", "STAFF"],
  "waitlist.manage": ["OWNER", "MANAGER", "HOST"],
  "turnover.view": ["OWNER", "MANAGER", "HOST"],
  "analytics.view_export": ["OWNER", "MANAGER", "VIEWER"],
  "ml_review.label": ["OWNER", "MANAGER"],
  "ml_review.export": ["OWNER"],
  "venues.manage": ["OWNER", "MANAGER"],
  "cameras.manage": ["OWNER", "MANAGER"],
  "polygons.calibrate": ["OWNER", "MANAGER"],
  "alert_rules.manage": ["OWNER", "MANAGER"],
  "users.manage_standard": ["OWNER", "MANAGER"],
  "users.manage_privileged": ["OWNER"],
  "audit_logs.view": ["OWNER", "MANAGER"],
  "system.manage": ["OWNER"],
  "privacy.purge": ["OWNER"],
  "tables.read": ["OWNER", "MANAGER", "HOST", "VIEWER"],
  "tables.manage": ["OWNER", "MANAGER"],
  "menu.read": ["OWNER", "MANAGER", "HOST", "STAFF", "VIEWER"],
  "menu.manage": ["OWNER", "MANAGER"],
  "menu.availability": ["OWNER", "MANAGER"],
  "menu.currency_manage": ["OWNER"],
  "qr.read": ["OWNER", "MANAGER", "HOST", "VIEWER"],
  "qr.manage": ["OWNER", "MANAGER"],
};

export interface ConditionalHostFlags {
  allowHostCameraView?: boolean;
  allowHostMenuAvailability?: boolean;
}

export function hasCapability(
  role: Role | undefined | null,
  capability: Capability,
  flagsOrCamView: boolean | ConditionalHostFlags = false,
): boolean {
  if (!role) return false;
  const opts: ConditionalHostFlags =
    typeof flagsOrCamView === "boolean"
      ? { allowHostCameraView: flagsOrCamView }
      : flagsOrCamView;
  if (capability === "cameras.live.view" && role === "HOST" && opts.allowHostCameraView) {
    return true;
  }
  if (capability === "menu.availability" && role === "HOST" && opts.allowHostMenuAvailability) {
    return true;
  }
  return CAPABILITY_ROLES[capability].includes(role);
}

export function defaultHomeForRole(role: Role, venueId?: string): string {
  if (!venueId) return "/onboarding";
  if (role === "STAFF") return `/venues/${venueId}/alerts`;
  if (role === "VIEWER") return `/venues/${venueId}/analytics`;
  return `/venues/${venueId}/floor`;
}
