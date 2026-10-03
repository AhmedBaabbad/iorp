import { PermissionGate } from "@/features/auth/permission-gate";
import { DemandList } from "@/features/production-demands/list";
import { P } from "@/lib/production-permissions";
export default function Page() { return <PermissionGate code={P.DEMANDS_READ}><DemandList /></PermissionGate>; }
