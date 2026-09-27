"use client";

import { usePermission } from "@/features/auth";
import { AdminRoleDetail } from "@/features/admin-roles";
import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";

export default function Page() {
  return usePermission("foundation:roles:read") ? <AdminRoleDetail /> : <AccessDeniedMessage />;
}
