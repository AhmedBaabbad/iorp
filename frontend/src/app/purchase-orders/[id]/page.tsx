import { OrderDetail } from "@/features/procurement";
import { PermissionGate } from "@/features/auth/permission-gate";
import { PR } from "@/lib/procurement-permissions";

type PageProps = { params: Promise<{ id: string }> };

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <PermissionGate code={PR.PO_READ}><OrderDetail orderId={id} /></PermissionGate>;
}
