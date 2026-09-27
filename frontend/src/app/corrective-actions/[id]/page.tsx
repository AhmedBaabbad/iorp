import { CorrectiveActionDetail } from "@/features/corrective-actions";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <CorrectiveActionDetail correctiveActionId={id} />;
}
