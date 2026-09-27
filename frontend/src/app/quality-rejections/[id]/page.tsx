import { QualityRejectionDetail } from "@/features/quality-rejections";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <QualityRejectionDetail rejectionId={id} />;
}
