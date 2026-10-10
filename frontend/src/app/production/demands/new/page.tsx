import { Suspense } from "react";
import { PermissionGate } from "@/features/auth/permission-gate";
import { NewDemand } from "@/features/production-demands/new-demand";
import { P } from "@/lib/production-permissions";
export default function Page() { return <PermissionGate code={P.DEMANDS_CREATE}><Suspense><NewDemand /></Suspense></PermissionGate>; }
