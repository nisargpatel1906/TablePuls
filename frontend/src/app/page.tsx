"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { defaultHomeForRole } from "@/lib/rbac";

export default function HomePage() {
  const { user, venues, loading, bootstrapRequired } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (bootstrapRequired) {
      router.replace("/register?bootstrap=true");
      return;
    }
    if (!user) {
      router.replace("/login");
      return;
    }
    router.replace(defaultHomeForRole(user.role, venues[0]?.id));
  }, [loading, bootstrapRequired, user, venues, router]);

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="tp-card p-6 text-sm text-[var(--tp-label-secondary)]">
        Loading TablePulse...
      </div>
    </div>
  );
}
