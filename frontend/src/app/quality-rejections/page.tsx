import { Suspense } from "react";
import { QualityRejectionsList } from "@/features/quality-rejections";
import { PermissionGate } from "@/features/auth/permission-gate";
import { Q } from "@/lib/quality-permissions";

export default function Page() {
  return <PermissionGate code={Q.REJECTIONS_READ}><Suspense fallback={null}><QualityRejectionsList /></Suspense></PermissionGate>;
}
