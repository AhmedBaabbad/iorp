import { PermissionGate } from "@/features/auth/permission-gate";
import { DemandForm } from "@/features/production-demands/form";
import { P } from "@/lib/production-permissions";
export default function Page() { return <PermissionGate code={P.DEMANDS_CREATE}><DemandForm /></PermissionGate>; }
