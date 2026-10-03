import { Suspense } from "react";
import { DowntimeEventForm } from "@/features/downtime-events";
import { PermissionGate } from "@/features/auth/permission-gate";
import { P } from "@/lib/production-permissions";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <PermissionGate code={P.DOWNTIME_UPDATE}><Suspense fallback={null}><DowntimeEventForm eventId={id} /></Suspense></PermissionGate>;
}
