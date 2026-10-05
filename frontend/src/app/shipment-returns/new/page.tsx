import { ReturnForm } from "@/features/shipments";
import { PermissionGate } from "@/features/auth/permission-gate";
import { S } from "@/lib/shipping-permissions";

type PageProps = { searchParams: Promise<{ shipment?: string }> };

// A customer's return, registered from its delivered note (?shipment=<id>).
export default async function Page({ searchParams }: PageProps) {
  const { shipment } = await searchParams;
  return <PermissionGate code={S.RETURNS_CREATE}><ReturnForm shipmentId={shipment ?? ""} /></PermissionGate>;
}
