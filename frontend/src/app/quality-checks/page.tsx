import { Suspense } from "react";
import { QualityChecksList } from "@/features/quality-checks";
import { PermissionGate } from "@/features/auth/permission-gate";
import { Q } from "@/lib/quality-permissions";

export default function Page() {
  return <PermissionGate code={Q.CHECKS_READ}><Suspense fallback={null}><QualityChecksList /></Suspense></PermissionGate>;
}
