"use client";

import type { ReactNode } from "react";
import { usePermission } from "@/features/auth/permission-hooks";

type PermissionGuardProps = {
  code: string;
  fallback?: ReactNode;
  children: ReactNode;
};

export function PermissionGuard({ code, fallback = null, children }: PermissionGuardProps) {
  const hasPermission = usePermission(code);
  return hasPermission ? <>{children}</> : <>{fallback}</>;
}
