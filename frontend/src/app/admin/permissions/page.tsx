"use client";

import { usePermission } from "@/features/auth";
import { AdminPermissionsList } from "@/features/admin-permissions";
import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";

export default function Page() {
  return usePermission("foundation:permissions:read") ? <AdminPermissionsList /> : <AccessDeniedMessage />;
}
