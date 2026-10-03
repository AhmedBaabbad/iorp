import { NcrReportsList } from "@/features/ncr-reports";
import { PermissionGate } from "@/features/auth/permission-gate";
import { Q } from "@/lib/quality-permissions";

export default function Page() {
  return <PermissionGate code={Q.NCR_READ}><NcrReportsList /></PermissionGate>;
}
