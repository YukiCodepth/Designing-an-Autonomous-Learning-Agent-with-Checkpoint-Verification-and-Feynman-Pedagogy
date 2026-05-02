"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";

import { useAuth } from "./auth-provider";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      const target = pathname ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${target}`);
    }
  }, [loading, pathname, router, user]);

  if (loading) {
    return <div className="panel empty">Restoring your session...</div>;
  }

  if (!user) {
    return <div className="panel empty">Redirecting to login...</div>;
  }

  return <>{children}</>;
}
