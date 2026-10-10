import { Suspense } from "react";
import { DashboardWorkspace } from "@/features/dashboard/DashboardWorkspace";
export default function Page() { return <Suspense><DashboardWorkspace department="procurement" /></Suspense>; }
