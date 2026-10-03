import { ShiftEditPage } from "@/features/shifts/components/ShiftEditPage";
import { PermissionGate } from "@/features/auth/permission-gate";
import { P } from "@/lib/production-permissions";

export default function Page() {
  return <PermissionGate code={P.SHIFTS_UPDATE}><ShiftEditPage /></PermissionGate>;
}
