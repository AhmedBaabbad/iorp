import { PermissionGate } from "@/features/auth/permission-gate";
import { DemandDetail } from "@/features/production-demands/detail";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <PermissionGate code="production:demands:read"><DemandDetail id={id} /></PermissionGate>; }
