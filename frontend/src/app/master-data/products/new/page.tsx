import { ProductForm } from "@/features/masterdata";
import { PermissionGate } from "@/features/auth/permission-gate";
import { MD } from "@/lib/masterdata-permissions";

type PageProps = { searchParams: Promise<{ name?: string; key?: string }> };

// A new product, or one made from a legacy product type (?name=…&key=…).
export default async function Page({ searchParams }: PageProps) {
  const { name, key } = await searchParams;
  return <PermissionGate code={MD.PRODUCTS_CREATE}><ProductForm initialName={name} initialKey={key} /></PermissionGate>;
}
