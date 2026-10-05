import { CorrectiveActionsList } from "@/features/ncr-reports";
import { PermissionGate } from "@/features/auth/permission-gate";
import { Q } from "@/lib/quality-permissions";

// Corrective actions across non-conformance reports (QUAL-NCR-002).
export default function Page() {
  return <PermissionGate anyOf={[Q.NCR_ACTIONS_READ, Q.NCR_READ]}><CorrectiveActionsList /></PermissionGate>;
}
