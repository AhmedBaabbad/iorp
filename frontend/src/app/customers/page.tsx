import { Suspense } from "react";

import { CustomersListPage } from "@/features/customers";

export default function Page() {
  return <Suspense><CustomersListPage /></Suspense>;
}
