import { DowntimeEventDetail } from "@/features/downtime-events";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <DowntimeEventDetail downtimeEventId={id} />;
}
