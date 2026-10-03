import { WorkCenterEditPage } from "@/features/work-centers/components/WorkCenterEditPage";
import { PermissionGate } from "@/features/auth/permission-gate";
import { P } from "@/lib/production-permissions";

export default function Page() {
  return <PermissionGate code={P.WORK_CENTERS_UPDATE}><WorkCenterEditPage /></PermissionGate>;
}
