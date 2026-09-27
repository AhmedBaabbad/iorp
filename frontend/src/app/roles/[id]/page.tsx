import { RoleDetailPage } from "@/features/roles";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RoleDetailPage id={id} />;
}
