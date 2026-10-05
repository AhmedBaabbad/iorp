import { ReturnsList } from "@/features/shipments";
import { PermissionGate } from "@/features/auth/permission-gate";
import { S } from "@/lib/shipping-permissions";

export default function Page() {
  return <PermissionGate code={S.RETURNS_READ}><ReturnsList /></PermissionGate>;
}
