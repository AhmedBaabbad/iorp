import { ResultsList } from "@/features/production-results";
import { PermissionGate } from "@/features/auth/permission-gate";
import { P } from "@/lib/production-permissions";

export default function Page() {
  return <PermissionGate code={P.RESULTS_READ}><ResultsList /></PermissionGate>;
}
