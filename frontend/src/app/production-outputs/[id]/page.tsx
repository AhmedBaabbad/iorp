import { ProductionOutputDetail } from "@/features/production-outputs";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <ProductionOutputDetail productionOutputId={id} />;
}
