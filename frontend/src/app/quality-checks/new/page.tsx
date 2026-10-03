import { Suspense } from "react";
import { QualityCheckForm } from "@/features/quality-checks";
import { PermissionGate } from "@/features/auth/permission-gate";
import { Q } from "@/lib/quality-permissions";

export default function Page() {
  return <PermissionGate code={Q.CHECKS_CREATE}><Suspense fallback={null}><QualityCheckForm /></Suspense></PermissionGate>;
}
