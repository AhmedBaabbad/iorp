import { OrderForm } from "@/features/procurement";
import { PermissionGate } from "@/features/auth/permission-gate";
import { PR } from "@/lib/procurement-permissions";

type PageProps = { searchParams: Promise<{ supplier?: string }> };

// A new purchase order, from a supplier's page (?supplier=<id>) or chosen here.
export default async function Page({ searchParams }: PageProps) {
  const { supplier } = await searchParams;
  return <PermissionGate code={PR.PO_CREATE}><OrderForm supplierId={supplier} /></PermissionGate>;
}
