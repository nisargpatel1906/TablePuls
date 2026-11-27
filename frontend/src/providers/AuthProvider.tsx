"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  apiFetch,
  type AuthUser,
  type OrgPolicies,
  refreshAccessToken,
  setAccessToken,
  type VenueSummary,
} from "@/lib/api";
import type { Locale } from "@/lib/i18n";

const DEFAULT_POLICIES: OrgPolicies = {
  require_2fa_roles: [],
  managers_can_manage_tables: true,
  managers_can_manage_menu: true,
  admins_can_manage_tables: true,
  admins_can_manage_menu: true,
};

interface AuthContextValue {
  user: AuthUser | null;
  venues: VenueSummary[];
  policies: OrgPolicies;
  loading: boolean;
  demoMode: boolean;
  bootstrapRequired: boolean;
  theme: "light" | "dark";
  solidMode: boolean;
  locale: Locale;
  toggleTheme: () => void;
  toggleSolidMode: () => void;
  toggleLocale: () => void;
  setSession: (token: string, user: AuthUser) => Promise<void>;
  refreshSessionData: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 3000,
    },
  },
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [venues, setVenues] = useState<VenueSummary[]>([]);
  const [policies, setPolicies] = useState<OrgPolicies>(DEFAULT_POLICIES);
  const [loading, setLoading] = useState(true);
  const [demoMode, setDemoMode] = useState(
    process.env.NEXT_PUBLIC_DEMO_MODE === "true",
  );
  const [bootstrapRequired, setBootstrapRequired] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [solidMode, setSolidMode] = useState(false);
  const [locale, setLocale] = useState<Locale>("en");

  const refreshSessionData = useCallback(async () => {
    try {
      const me = await apiFetch<{
        user: AuthUser;
        venues: VenueSummary[];
        policies?: OrgPolicies;
      }>("/api/v1/auth/me");
      setUser(me.user);
      setVenues(me.venues);
      if (me.policies) {
        setPolicies(me.policies);
      }
    } catch {
      setUser(null);
      setVenues([]);
      setPolicies(DEFAULT_POLICIES);
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      let hasSession = false;
      try {
        const status = await apiFetch<{
          bootstrap_required: boolean;
          demo_mode: boolean;
          has_session?: boolean;
        }>("/api/v1/auth/bootstrap-status", { skipAuth: true, retryOn401: false });
        if (active) {
          setBootstrapRequired(status.bootstrap_required);
          setDemoMode(status.demo_mode);
          hasSession = Boolean(status.has_session);
        }
      } catch {
        // Ignore startup check error; login page handles degraded API
      }

      if (hasSession) {
        const token = await refreshAccessToken();
        if (token && active) {
          await refreshSessionData();
        }
      }
      if (active) {
        setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [refreshSessionData]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setInterval(() => {
      void refreshAccessToken();
    }, 12 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [user]);

  useEffect(() => {
    const html = document.documentElement;
    if (theme === "dark") {
      html.classList.add("dark");
    } else {
      html.classList.remove("dark");
    }
    if (solidMode) {
      html.classList.add("solid-mode");
    } else {
      html.classList.remove("solid-mode");
    }
  }, [theme, solidMode]);

  const setSession = useCallback(
    async (token: string, nextUser: AuthUser) => {
      setAccessToken(token);
      setBootstrapRequired(false);
      await refreshSessionData();
      setUser((prev) => prev ?? nextUser);
    },
    [refreshSessionData],
  );

  const signOut = useCallback(async () => {
    try {
      await apiFetch("/api/v1/auth/logout", { method: "POST" });
    } catch {
      // Clear client memory regardless
    } finally {
      setAccessToken(null);
      setUser(null);
      setVenues([]);
      setPolicies(DEFAULT_POLICIES);
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  }, []);

  const toggleSolidMode = useCallback(() => {
    setSolidMode((prev) => !prev);
  }, []);

  const toggleLocale = useCallback(() => {
    setLocale((prev) => (prev === "en" ? "hi" : "en"));
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider
        value={{
          user,
          venues,
          policies,
          loading,
          demoMode,
          bootstrapRequired,
          theme,
          solidMode,
          locale,
          toggleTheme,
          toggleSolidMode,
          toggleLocale,
          setSession,
          refreshSessionData,
          signOut,
        }}
      >
        {children}
      </AuthContext.Provider>
    </QueryClientProvider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
