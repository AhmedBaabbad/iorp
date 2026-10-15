"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";

import { usePlatformAuth } from "./platform-auth-context";

export function PlatformProtectedRoute({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isLoading, account } = usePlatformAuth();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/platform/login");
    }
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (account?.mfa_enrollment_required && pathname !== "/platform/security") router.replace("/platform/security");
  }, [account, pathname, router]);

  if (isLoading || !isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
