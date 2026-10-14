import { AuditLogDetailPage } from "@/features/admin-audit/AuditLogPage";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AuditLogDetailPage id={id} />;
}
