import type { Role } from "./rbac";

export interface AuthUser {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  role: Role;
  assigned_venue_ids: string[];
  is_active: boolean;
  totp_enabled?: boolean;
  recovery_codes_remaining?: number;
}

export interface OrgPolicies {
  require_2fa_roles: Role[];
  managers_can_manage_tables: boolean;
  managers_can_manage_menu: boolean;
  admins_can_manage_tables: boolean;
  admins_can_manage_menu: boolean;
}

export interface VenueSummary {
  id: string;
  name: string;
  timezone: string;
  allow_host_camera_view: boolean;
  allow_host_menu_availability?: boolean;
  guests_per_server_ratio?: number;
  currency_code?: string;
  menu_public_enabled?: boolean;
  show_unavailable_items_public?: boolean;
  menu_tagline?: string | null;
  logo_storage_key?: string | null;
  menu_revision?: number;
  qr_grace_days?: number;
}

export class ApiError extends Error {
  status: number;
  code: string;
  fields?: Record<string, string>;

  constructor(status: number, code: string, message: string, fields?: Record<string, string>) {
    super(message);
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

// In-memory access token ONLY (never localStorage or sessionStorage, per AGENTS.md §6)
let inMemoryAccessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

export function apiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
}

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const res = await fetch(`${apiBaseUrl()}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        inMemoryAccessToken = null;
        return null;
      }
      const json = await res.json();
      const token = json?.data?.access_token as string | undefined;
      inMemoryAccessToken = token ?? null;
      return inMemoryAccessToken;
    } catch {
      inMemoryAccessToken = null;
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { skipAuth?: boolean; retryOn401?: boolean } = {},
): Promise<T> {
  const { skipAuth = false, retryOn401 = true, headers, ...rest } = options;
  const reqHeaders = new Headers(headers);
  if (!reqHeaders.has("Content-Type") && !(rest.body instanceof FormData)) {
    reqHeaders.set("Content-Type", "application/json");
  }
  if (!skipAuth && inMemoryAccessToken) {
    reqHeaders.set("Authorization", `Bearer ${inMemoryAccessToken}`);
  }

  let res = await fetch(`${apiBaseUrl()}${path}`, {
    ...rest,
    headers: reqHeaders,
    credentials: "include",
  });

  if (res.status === 401 && !skipAuth && retryOn401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      reqHeaders.set("Authorization", `Bearer ${refreshed}`);
      res = await fetch(`${apiBaseUrl()}${path}`, {
        ...rest,
        headers: reqHeaders,
        credentials: "include",
      });
    }
  }

  const contentType = res.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    if (!res.ok) {
      throw new ApiError(res.status, "HTTP_ERROR", `Request failed with status ${res.status}`);
    }
    return (await res.blob()) as unknown as T;
  }

  const payload = await res.json();
  if (!res.ok || payload?.success === false) {
    const err = payload?.error ?? {};
    throw new ApiError(
      res.status,
      String(err.code || "INTERNAL_ERROR"),
      String(err.message || "Request failed"),
      err.fields as Record<string, string> | undefined,
    );
  }
  return payload.data as T;
}
