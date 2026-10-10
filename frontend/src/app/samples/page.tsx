import { Suspense } from "react";

import { SamplesList } from "@/features/samples";

export default function Page() {
  return <Suspense><SamplesList /></Suspense>;
}
