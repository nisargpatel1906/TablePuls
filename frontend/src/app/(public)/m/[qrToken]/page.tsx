"use client";

import React, { Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { PublicDigitalMenu } from "@/components/PublicDigitalMenu";

function CustomerMenuRouteInner() {
  const params = useParams<{ qrToken: string }>();
  const searchParams = useSearchParams();
  const qrToken = params?.qrToken || "";
  const previewParam = searchParams.get("p");
  const rawTheme = searchParams.get("theme");
  const initialTheme = rawTheme === "dark" ? "dark" : "light";

  return (
    <PublicDigitalMenu
      qrToken={qrToken}
      previewParam={previewParam}
      initialTheme={initialTheme}
    />
  );
}

export default function CustomerMenuPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[var(--bg-canvas)] p-6 text-center text-sm text-[var(--text-secondary)]">
          Loading digital menu...
        </div>
      }
    >
      <CustomerMenuRouteInner />
    </Suspense>
  );
}
