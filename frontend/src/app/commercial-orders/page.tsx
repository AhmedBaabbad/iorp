import { Suspense } from "react";

import { CommercialOrdersList } from "@/features/commercial-orders";

export default function Page() {
  return <Suspense><CommercialOrdersList /></Suspense>;
}
