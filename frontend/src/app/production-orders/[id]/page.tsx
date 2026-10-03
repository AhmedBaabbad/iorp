import { ProductionOrderDetail } from "@/features/production-orders";
import { PermissionGate } from "@/features/auth/permission-gate";
import { P } from "@/lib/production-permissions";

export default function Page() {
  return <PermissionGate code={P.ORDERS_READ}><ProductionOrderDetail /></PermissionGate>;
}
