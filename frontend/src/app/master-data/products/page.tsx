import { ProductsList } from "@/features/masterdata";
import { PermissionGate } from "@/features/auth/permission-gate";
import { MD } from "@/lib/masterdata-permissions";

export default function Page() {
  return <PermissionGate code={MD.PRODUCTS_READ}><ProductsList /></PermissionGate>;
}
