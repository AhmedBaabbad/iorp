import { SupplierForm } from "@/features/procurement";
import { PermissionGate } from "@/features/auth/permission-gate";
import { PR } from "@/lib/procurement-permissions";

export default function Page() {
  return <PermissionGate code={PR.SUPPLIERS_CREATE}><SupplierForm /></PermissionGate>;
}
