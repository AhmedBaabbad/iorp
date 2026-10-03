import { Suspense } from "react";
import { DowntimeEventForm } from "@/features/downtime-events";
import { PermissionGate } from "@/features/auth/permission-gate";
import { P } from "@/lib/production-permissions";

export default function Page() {
  return <PermissionGate code={P.DOWNTIME_CREATE}><Suspense fallback={null}><DowntimeEventForm /></Suspense></PermissionGate>;
}
