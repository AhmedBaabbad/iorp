"use client";

import { useParams } from "next/navigation";

import { usePermission } from "@/features/auth";
import { AdminUserForm } from "@/features/admin-users";
import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";

export default function Page() {
  const params = useParams<{ id: string }>();
  return usePermission("foundation:users:write")
    ? <AdminUserForm userId={params.id} />
    : <AccessDeniedMessage />;
}
