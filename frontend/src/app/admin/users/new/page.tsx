"use client";

import { usePermission } from "@/features/auth";
import { AdminUserForm } from "@/features/admin-users";
import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";

export default function Page() {
  return usePermission("foundation:users:write") ? <AdminUserForm /> : <AccessDeniedMessage />;
}
