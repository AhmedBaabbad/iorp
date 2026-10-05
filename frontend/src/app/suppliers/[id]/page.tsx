import { SupplierDetail } from "@/features/procurement";
import { PermissionGate } from "@/features/auth/permission-gate";
import { PR } from "@/lib/procurement-permissions";

type PageProps = { params: Promise<{ id: string }> };

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <PermissionGate code={PR.SUPPLIERS_READ}><SupplierDetail supplierId={id} /></PermissionGate>;
}
