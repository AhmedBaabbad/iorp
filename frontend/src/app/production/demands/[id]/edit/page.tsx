import { PermissionGate } from "@/features/auth/permission-gate";
import { DemandForm } from "@/features/production-demands/form";
import { P } from "@/lib/production-permissions";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <PermissionGate code={P.DEMANDS_UPDATE}><DemandForm id={id} /></PermissionGate>; }
