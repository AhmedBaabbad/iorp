import { SampleDetail } from "@/features/samples";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <SampleDetail sampleId={id} />;
}
