import { QualityIncomingList } from "@/features/quality-checks/components/IncomingInspection";
import { PermissionGate } from "@/features/auth/permission-gate";
import { Q } from "@/lib/quality-permissions";

export default function Page() {
  return <PermissionGate code={Q.CHECKS_READ}><QualityIncomingList /></PermissionGate>;
}
