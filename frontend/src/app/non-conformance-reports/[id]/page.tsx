import { NcrReportDetail } from "@/features/ncr-reports";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <NcrReportDetail ncrReportId={id} />;
}
