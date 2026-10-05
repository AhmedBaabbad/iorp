import { NcrReportForm } from "@/features/ncr-reports";
import { PermissionGate } from "@/features/auth/permission-gate";
import { Q } from "@/lib/quality-permissions";

type PageProps = { params: Promise<{ id: string }> };

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <PermissionGate code={Q.NCR_UPDATE}><NcrReportForm reportId={id} /></PermissionGate>;
}
