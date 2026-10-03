import { Suspense } from "react";
import { DowntimeEventsList } from "@/features/downtime-events";
import { PermissionGate } from "@/features/auth/permission-gate";
import { P } from "@/lib/production-permissions";

export default function Page() {
  return <PermissionGate code={P.DOWNTIME_READ}><Suspense fallback={null}><DowntimeEventsList /></Suspense></PermissionGate>;
}
