import { PermissionGate } from "@/features/auth/permission-gate";
import { DemandDetail } from "@/features/production-demands/detail";
import { P } from "@/lib/production-permissions";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <PermissionGate code={P.DEMANDS_READ}><DemandDetail id={id} /></PermissionGate>; }
