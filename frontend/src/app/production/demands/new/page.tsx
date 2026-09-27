import { PermissionGate } from "@/features/auth/permission-gate";
import { DemandForm } from "@/features/production-demands/form";
export default function Page() { return <PermissionGate code="production:demands:create"><DemandForm /></PermissionGate>; }
