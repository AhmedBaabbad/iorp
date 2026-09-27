"use client";

import { useParams } from "next/navigation";

import { usePermission } from "@/features/auth";
import { AdminRoleForm } from "@/features/admin-roles";
import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";

export default function Page() {
  const params = useParams<{ id: string }>();
  return usePermission("foundation:roles:write")
    ? <AdminRoleForm roleId={params.id} />
    : <AccessDeniedMessage />;
}
