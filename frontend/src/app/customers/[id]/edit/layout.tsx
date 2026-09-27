import type { ReactNode } from "react";
import { PermissionGate } from "@/features/auth";
export default function Layout({ children }: { children: ReactNode }) {
  return <PermissionGate code="commercial:customers:update">{children}</PermissionGate>;
}
