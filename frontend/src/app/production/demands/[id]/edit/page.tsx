import { PermissionGate } from "@/features/auth/permission-gate";
import { DemandForm } from "@/features/production-demands/form";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <PermissionGate code="production:demands:update"><DemandForm id={id} /></PermissionGate>; }
