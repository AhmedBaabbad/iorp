import { Suspense } from "react";
import { QualityCheckForm } from "@/features/quality-checks";
import { PermissionGate } from "@/features/auth/permission-gate";
import { Q } from "@/lib/quality-permissions";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <PermissionGate code={Q.CHECKS_UPDATE}><Suspense fallback={null}><QualityCheckForm checkId={id} /></Suspense></PermissionGate>;
}
