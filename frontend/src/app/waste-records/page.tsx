import { Suspense } from "react";
import { WasteRecordsList } from "@/features/waste-records";
import { PermissionGate } from "@/features/auth/permission-gate";
import { P } from "@/lib/production-permissions";

export default function Page() {
  return <PermissionGate code={P.WASTE_READ}><Suspense fallback={null}><WasteRecordsList /></Suspense></PermissionGate>;
}
