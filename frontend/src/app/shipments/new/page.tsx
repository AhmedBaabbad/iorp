import { ShipmentForm } from "@/features/shipments";
import { PermissionGate } from "@/features/auth/permission-gate";
import { S } from "@/lib/shipping-permissions";

export default function Page() {
  return <PermissionGate code={S.SHIPMENTS_CREATE}><ShipmentForm /></PermissionGate>;
}
