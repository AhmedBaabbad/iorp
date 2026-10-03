import { Suspense } from "react";
import { QualityRejectionForm } from "@/features/quality-rejections";
import { PermissionGate } from "@/features/auth/permission-gate";
import { Q } from "@/lib/quality-permissions";

export default function Page() {
  return <PermissionGate code={Q.REJECTIONS_CREATE}><Suspense fallback={null}><QualityRejectionForm /></Suspense></PermissionGate>;
}
