import { ShiftDetail } from "@/features/shifts";
import { PermissionGate } from "@/features/auth/permission-gate";
import { P } from "@/lib/production-permissions";

export default function Page() {
  return <PermissionGate code={P.SHIFTS_READ}><ShiftDetail /></PermissionGate>;
}
