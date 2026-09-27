"use client";

import { usePermission } from "@/features/auth";
import { AdminRolesList } from "@/features/admin-roles";
import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";

export default function Page() {
  return usePermission("foundation:roles:read") ? <AdminRolesList /> : <AccessDeniedMessage />;
}
