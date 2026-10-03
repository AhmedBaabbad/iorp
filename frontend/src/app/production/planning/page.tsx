import { PermissionGate } from "@/features/auth/permission-gate";
import { DemandList } from "@/features/production-demands/list";
import { P } from "@/lib/production-permissions";
export default function Page() { return <PermissionGate code={P.PLANNING_READ}><DemandList planning /></PermissionGate>; }
