import { Suspense } from "react";

import { OrganizationStatusPage } from "@/features/auth/organization-status-page";

export default function Page() {
  return <Suspense fallback={null}><OrganizationStatusPage /></Suspense>;
}
