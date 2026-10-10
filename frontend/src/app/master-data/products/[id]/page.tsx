import { ProductForm } from "@/features/masterdata";
import { PermissionGate } from "@/features/auth/permission-gate";
import { MD } from "@/lib/masterdata-permissions";

type PageProps = { params: Promise<{ id: string }> };

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <PermissionGate code={MD.PRODUCTS_READ}><ProductForm productId={id} /></PermissionGate>;
}
