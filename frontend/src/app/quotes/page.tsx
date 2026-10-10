import { Suspense } from "react";

import { QuotesList } from "@/features/quotes";

export default function Page() {
  return <Suspense><QuotesList /></Suspense>;
}
