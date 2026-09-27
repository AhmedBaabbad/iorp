import { WasteRecordDetail } from "@/features/waste-records";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <WasteRecordDetail wasteRecordId={id} />;
}
