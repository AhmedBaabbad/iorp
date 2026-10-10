import { ReferenceLists } from "@/features/masterdata";
import { PermissionGate } from "@/features/auth/permission-gate";
import { MD } from "@/lib/masterdata-permissions";

type PageProps = { searchParams: Promise<{ list?: string }> };

// Sectors, opportunity sources, countries and cities (?list=city opens one).
export default async function Page({ searchParams }: PageProps) {
  const { list } = await searchParams;
  return <PermissionGate code={MD.LISTS_READ}><ReferenceLists initialList={list} /></PermissionGate>;
}
