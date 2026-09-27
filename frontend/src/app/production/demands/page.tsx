import { PermissionGate } from "@/features/auth/permission-gate";
import { DemandList } from "@/features/production-demands/list";
export default function Page() { return <PermissionGate code="production:demands:read"><DemandList /></PermissionGate>; }
