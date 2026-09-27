"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { usePlatformAuth } from "./platform-auth-context";

export function PlatformProtectedRoute({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isLoading } = usePlatformAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/platform/login");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading || !isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
