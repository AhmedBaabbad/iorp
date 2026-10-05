import { ShipmentDetail } from "@/features/shipments";
import { PermissionGate } from "@/features/auth/permission-gate";
import { S } from "@/lib/shipping-permissions";

type PageProps = { params: Promise<{ id: string }> };

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <PermissionGate code={S.SHIPMENTS_READ}><ShipmentDetail shipmentId={id} /></PermissionGate>;
}
