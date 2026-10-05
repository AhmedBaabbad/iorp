import { Suspense } from "react";
import { NcrReportForm } from "@/features/ncr-reports";
import { PermissionGate } from "@/features/auth/permission-gate";
import { Q } from "@/lib/quality-permissions";

// A new report; opened from a supplier or a goods receipt it arrives with ?supplier=&reference=&item=.
export default function Page() {
  return <PermissionGate code={Q.NCR_CREATE}><Suspense fallback={null}><NcrReportForm /></Suspense></PermissionGate>;
}
