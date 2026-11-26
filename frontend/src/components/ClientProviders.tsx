"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { AuthProvider } from "@/providers/AuthProvider";

export function ClientProviders({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname?.startsWith("/m/") || pathname === "/m") {
    return <>{children}</>;
  }
  return <AuthProvider>{children}</AuthProvider>;
}
