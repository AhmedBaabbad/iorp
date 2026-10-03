import { Suspense } from "react";
import { WasteRecordForm } from "@/features/waste-records";
import { PermissionGate } from "@/features/auth/permission-gate";
import { P } from "@/lib/production-permissions";

export default function Page() {
  return <PermissionGate code={P.WASTE_CREATE}><Suspense fallback={null}><WasteRecordForm /></Suspense></PermissionGate>;
}
