import { WasteRecordDetail } from "@/features/waste-records";
import { PermissionGate } from "@/features/auth/permission-gate";
import { P } from "@/lib/production-permissions";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <PermissionGate code={P.WASTE_READ}><WasteRecordDetail recordId={id} /></PermissionGate>;
}
