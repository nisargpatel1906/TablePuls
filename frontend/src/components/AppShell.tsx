"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  BarChart3,
  Bell,
  Camera,
  CheckSquare,
  Clock,
  Grid2x2,
  Languages,
  LogOut,
  Menu,
  Moon,
  PenTool,
  Shield,
  Sliders,
  Sun,
  Users,
  Video,
  X,
} from "lucide-react";
import { useAuth } from "@/providers/AuthProvider";
import { hasCapability } from "@/lib/rbac";
import { t } from "@/lib/i18n";

export type ConnectionState = "live" | "reconnecting" | "polling";

interface AppShellProps {
  venueId?: string;
  connectionState?: ConnectionState;
  occupiedSummary?: string;
  activeAlertsCount?: number;
  aiPaused?: boolean;
  toastMessage?: string | null;
  children: React.ReactNode;
}

export function AppShell({
  venueId,
  connectionState = "live",
  occupiedSummary,
  activeAlertsCount = 0,
  aiPaused = false,
  toastMessage = null,
  children,
}: AppShellProps) {
  const {
    user,
    venues,
    theme,
    solidMode,
    locale,
    toggleTheme,
    toggleSolidMode,
    toggleLocale,
    signOut,
  } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const activeVenueId = venueId || venues[0]?.id || "";
  const activeVenue = venues.find((v) => v.id === activeVenueId) || venues[0];
  const allowHostCam = Boolean(activeVenue?.allow_host_camera_view);

  const primaryNav = [
    {
      href: `/venues/${activeVenueId}/floor`,
      label: t(locale, "nav.floor"),
      icon: Grid2x2,
      show: Boolean(activeVenueId) && hasCapability(user?.role, "floor.view"),
    },
    {
      href: `/venues/${activeVenueId}/cameras/live`,
      label: t(locale, "nav.cameras"),
      icon: Video,
      show:
        Boolean(activeVenueId) &&
        hasCapability(user?.role, "cameras.live.view", allowHostCam),
    },
    {
      href: `/venues/${activeVenueId}/alerts`,
      label: t(locale, "nav.alerts"),
      icon: Bell,
      badge: activeAlertsCount,
      show: Boolean(activeVenueId) && hasCapability(user?.role, "alerts.view"),
    },
    {
      href: `/venues/${activeVenueId}/waitlist`,
      label: t(locale, "nav.waitlist"),
      icon: Clock,
      show: Boolean(activeVenueId) && hasCapability(user?.role, "waitlist.manage"),
    },
    {
      href: `/venues/${activeVenueId}/analytics`,
      label: t(locale, "nav.analytics"),
      icon: BarChart3,
      show:
        Boolean(activeVenueId) &&
        hasCapability(user?.role, "analytics.view_export"),
    },
    {
      href: `/venues/${activeVenueId}/ml-review`,
      label: t(locale, "nav.ml_review"),
      icon: CheckSquare,
      show: Boolean(activeVenueId) && hasCapability(user?.role, "ml_review.label"),
    },
  ].filter((item) => item.show);

  const adminNav = [
    {
      href: `/venues/${activeVenueId}/settings/cameras`,
      label: t(locale, "nav.cam_settings"),
      icon: Camera,
      show: Boolean(activeVenueId) && hasCapability(user?.role, "cameras.manage"),
    },
    {
      href: `/venues/${activeVenueId}/settings/alerts`,
      label: t(locale, "nav.alert_rules"),
      icon: Sliders,
      show:
        Boolean(activeVenueId) && hasCapability(user?.role, "alert_rules.manage"),
    },
    {
      href: `/org/users`,
      label: t(locale, "nav.users"),
      icon: Users,
      show: hasCapability(user?.role, "users.manage_standard"),
    },
    {
      href: `/org/system`,
      label: t(locale, "nav.system"),
      icon: Shield,
      show: hasCapability(user?.role, "system.manage"),
    },
  ].filter((item) => item.show);

  const connDot =
    connectionState === "live"
      ? "bg-[#34C759]"
      : connectionState === "reconnecting"
        ? "bg-[#FF9500]"
        : "bg-[#8E8E93]";
  const connLabel =
    connectionState === "live"
      ? t(locale, "status.live")
      : connectionState === "reconnecting"
        ? t(locale, "status.reconnecting")
        : t(locale, "status.polling");

  const handleSignOut = async () => {
    await signOut();
    router.push("/login");
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* Desktop Sticky Liquid Glass Sidebar */}
      <aside
        aria-label="Primary navigation"
        className="hidden lg:flex lg:w-60 lg:flex-col lg:sticky lg:top-3 lg:h-[calc(100vh-24px)] lg:ml-3 lg:my-3 tp-glass rounded-[24px] p-3 shrink-0"
      >
        <div className="flex items-center gap-2.5 px-2 pb-2.5 border-b border-[var(--tp-separator)]">
          <div className="h-9 w-9 rounded-xl bg-[var(--tp-label-primary)] text-[var(--tp-surface)] flex items-center justify-center font-bold">
            <PenTool className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <div className="text-sm font-bold leading-tight">TablePulse</div>
            <div className="text-[11px] text-[var(--tp-label-secondary)]">
              {user?.role || "Guest"}
            </div>
          </div>
        </div>

        {venues.length > 0 && (
          <div className="mt-2 px-0.5">
            <label htmlFor="venue-switcher" className="sr-only">
              Select venue
            </label>
            <select
              id="venue-switcher"
              value={activeVenueId}
              onChange={(e) => router.push(`/venues/${e.target.value}/floor`)}
              className="w-full min-h-[36px] rounded-[12px] bg-[var(--tp-inset-field)] px-2.5 text-xs font-medium text-[var(--tp-label-primary)] border border-[var(--tp-card-border)]"
            >
              {venues.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <nav className="mt-2.5 flex-1 space-y-0.5 overflow-y-auto">
          {primaryNav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center justify-between min-h-[36px] px-2.5 py-1 rounded-xl text-[13px] font-medium transition ${
                  active
                    ? "bg-[var(--tp-accent)] text-white"
                    : "text-[var(--tp-label-primary)] hover:bg-[var(--tp-inset-field)]"
                }`}
              >
                <span className="flex items-center gap-2">
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {item.label}
                </span>
                {typeof item.badge === "number" && item.badge > 0 && (
                  <span className="rounded-full bg-[#FF3B30] px-1.5 py-0.5 text-[11px] font-bold text-white tabular-nums">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}

          {adminNav.length > 0 && (
            <div className="pt-2 mt-1.5 border-t border-[var(--tp-separator)] space-y-0.5">
              <div className="px-2.5 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--tp-label-secondary)]">
                Admin
              </div>
              {adminNav.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-2 min-h-[36px] px-2.5 py-1 rounded-xl text-[13px] font-medium transition ${
                      active
                        ? "bg-[var(--tp-accent)] text-white"
                        : "text-[var(--tp-label-primary)] hover:bg-[var(--tp-inset-field)]"
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          )}
        </nav>

        <button
          type="button"
          onClick={handleSignOut}
          className="mt-1.5 flex items-center gap-2 min-h-[36px] px-2.5 rounded-xl text-[13px] font-medium text-[var(--tp-label-secondary)] hover:bg-[var(--tp-inset-field)] hover:text-[var(--tp-label-primary)]"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          {t(locale, "action.sign_out")}
        </button>
      </aside>

      {/* Main Content Column */}
      <div className="flex-1 flex flex-col min-w-0 pb-24 lg:pb-6">
        {/* Top Floating Status Bar */}
        <header className="sticky top-0 lg:top-3.5 z-30 mx-3 lg:mx-6 mt-3 flex flex-wrap items-center justify-between gap-2 rounded-full tp-glass px-3.5 py-2">
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Open navigation menu"
              className="lg:hidden inline-flex h-11 w-11 items-center justify-center rounded-full hover:bg-[var(--tp-inset-field)]"
            >
              <Menu className="h-5 w-5" aria-hidden="true" />
            </button>
            <span className="inline-flex items-center gap-2 rounded-full bg-[var(--tp-inset-field)] px-3 py-1.5 text-xs font-semibold">
              <span className={`h-2.5 w-2.5 rounded-full ${connDot}`} aria-hidden="true" />
              <span>{connLabel}</span>
            </span>
            {occupiedSummary && (
              <span className="hidden sm:inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--tp-label-secondary)] tabular-nums">
                <Activity className="h-3.5 w-3.5" aria-hidden="true" />
                {occupiedSummary}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5">
            {aiPaused && (
              <span className="rounded-full bg-[#FF9500]/20 text-[#9A4E00] dark:text-[#FFB340] px-3 py-1 text-xs font-semibold">
                {t(locale, "status.ai_paused")}
              </span>
            )}
            <button
              type="button"
              onClick={toggleLocale}
              aria-label="Toggle language EN/HI"
              className="inline-flex h-11 px-3 items-center gap-1 rounded-full hover:bg-[var(--tp-inset-field)] text-xs font-semibold"
            >
              <Languages className="h-4 w-4" aria-hidden="true" />
              {locale.toUpperCase()}
            </button>
            <button
              type="button"
              onClick={toggleSolidMode}
              aria-label="Toggle reduce transparency"
              aria-pressed={solidMode}
              className="hidden sm:inline-flex h-11 px-3 items-center rounded-full hover:bg-[var(--tp-inset-field)] text-xs font-semibold"
            >
              {solidMode ? t(locale, "surface.solid") : t(locale, "surface.glass")}
            </button>
            <button
              type="button"
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="inline-flex h-11 w-11 items-center justify-center rounded-full hover:bg-[var(--tp-inset-field)]"
            >
              {theme === "dark" ? (
                <Sun className="h-4 w-4" aria-hidden="true" />
              ) : (
                <Moon className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </header>

        {toastMessage && (
          <div
            role="status"
            aria-live="polite"
            className="mx-auto mt-3 rounded-full tp-glass px-4 py-2 text-xs font-semibold text-[var(--tp-label-primary)]"
          >
            {toastMessage}
          </div>
        )}

        <main className="flex-1 px-3 lg:px-6 pt-4 pb-24 lg:pb-6">{children}</main>
      </div>

      {/* Mobile / Tablet Bottom Dock (<1024px) */}
      <nav
        aria-label="Bottom dock"
        className="lg:hidden fixed bottom-3 left-3 right-3 z-40 tp-glass rounded-full px-2 py-1.5 flex items-center justify-around"
      >
        <Link
          href={`/venues/${activeVenueId}/floor`}
          className="flex flex-col items-center justify-center min-h-[44px] min-w-[60px] text-xs font-medium"
        >
          <Grid2x2 className="h-4 w-4" aria-hidden="true" />
          <span>{t(locale, "nav.floor")}</span>
        </Link>
        <Link
          href={`/venues/${activeVenueId}/alerts`}
          className="flex flex-col items-center justify-center min-h-[44px] min-w-[60px] text-xs font-medium"
        >
          <Bell className="h-4 w-4" aria-hidden="true" />
          <span>{t(locale, "nav.alerts")} ({activeAlertsCount})</span>
        </Link>
        <Link
          href={`/venues/${activeVenueId}/waitlist`}
          className="flex flex-col items-center justify-center min-h-[44px] min-w-[60px] text-xs font-medium"
        >
          <Clock className="h-4 w-4" aria-hidden="true" />
          <span>{t(locale, "nav.waitlist")}</span>
        </Link>
        <button
          type="button"
          onClick={() => setMobileMenuOpen(true)}
          className="flex flex-col items-center justify-center min-h-[44px] min-w-[60px] text-xs font-medium"
        >
          <Menu className="h-4 w-4" aria-hidden="true" />
          <span>{t(locale, "nav.more")}</span>
        </button>
      </nav>

      {/* Mobile Full Glass Menu Drawer */}
      {mobileMenuOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
          className="fixed inset-0 z-50 bg-black/40 flex justify-end lg:hidden"
        >
          <div className="w-80 max-w-full h-full tp-glass p-5 flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-[var(--tp-separator)]">
              <span className="text-base font-bold">TablePulse Menu</span>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                aria-label="Close navigation menu"
                className="h-11 w-11 inline-flex items-center justify-center rounded-full"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            <div className="mt-4 flex-1 space-y-1 overflow-y-auto">
              {[...primaryNav, ...adminNav].map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center gap-3 min-h-[44px] px-3 rounded-2xl text-sm font-medium hover:bg-[var(--tp-inset-field)]"
                  >
                    <Icon className="h-4 w-4" aria-hidden="true" />
                    {item.label}
                  </Link>
                );
              })}
            </div>
            <button
              type="button"
              onClick={handleSignOut}
              className="mt-4 flex items-center gap-2.5 min-h-[44px] px-3 rounded-2xl text-sm font-medium text-[#FF3B30]"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              {t(locale, "action.sign_out")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
