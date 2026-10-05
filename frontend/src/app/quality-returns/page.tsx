import { QualityReturnsList } from "@/features/quality-checks/components/QualityReturnsList";
import { PermissionGate } from "@/features/auth/permission-gate";
import { Q } from "@/lib/quality-permissions";

export default function Page() {
  return <PermissionGate code={Q.CHECKS_READ}><QualityReturnsList /></PermissionGate>;
}
