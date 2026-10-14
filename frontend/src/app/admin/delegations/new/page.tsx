"use client";

import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";
import { useHasAnyPermission } from "@/features/auth/permission-hooks";
import { DelegationForm } from "@/features/delegations/DelegationsPage";
import { DELEGATIONS_PAGE } from "@/lib/delegations";

export default function Page() {
  const allowed = useHasAnyPermission(DELEGATIONS_PAGE);
  return allowed ? <DelegationForm /> : <AccessDeniedMessage />;
}
