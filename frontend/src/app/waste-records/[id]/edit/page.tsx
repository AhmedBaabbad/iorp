import { Suspense } from "react";
import { WasteRecordForm } from "@/features/waste-records";
import { PermissionGate } from "@/features/auth/permission-gate";
import { P } from "@/lib/production-permissions";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <PermissionGate code={P.WASTE_UPDATE}><Suspense fallback={null}><WasteRecordForm recordId={id} /></Suspense></PermissionGate>;
}
