"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { RoleForm } from "@/features/roles";
import { getRole } from "@/features/roles/api/roles-api";
import type { RoleDetail } from "@/features/roles/types";

export default function Page() {
  const params = useParams<{ id: string }>();
  const [role, setRole] = useState<RoleDetail | null>(null);

  useEffect(() => {
    if (params.id) {
      void getRole(params.id).then(setRole);
    }
  }, [params.id]);

  if (!role) return null;
  return <RoleForm role={role} />;
}
