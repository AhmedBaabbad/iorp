import { Suspense } from "react";

import { PermissionGate } from "@/features/auth/permission-gate";
import { DashboardWorkspace } from "@/features/dashboard/DashboardWorkspace";
import { P } from "@/lib/production-permissions";

export default function Page() {
  return (
    <PermissionGate anyOf={[P.ORDERS_READ, P.RESULTS_READ, P.DOWNTIME_READ, P.DEMANDS_READ]}>
      <Suspense><DashboardWorkspace department="production" /></Suspense>
    </PermissionGate>
  );
}
