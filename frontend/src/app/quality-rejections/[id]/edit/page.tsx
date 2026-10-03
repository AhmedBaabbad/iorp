import { Suspense } from "react";
import { QualityRejectionForm } from "@/features/quality-rejections";
import { PermissionGate } from "@/features/auth/permission-gate";
import { Q } from "@/lib/quality-permissions";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <PermissionGate code={Q.REJECTIONS_UPDATE}><Suspense fallback={null}><QualityRejectionForm rejectionId={id} /></Suspense></PermissionGate>;
}
