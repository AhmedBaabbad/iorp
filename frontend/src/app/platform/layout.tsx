import type { ReactNode } from "react";

import { PlatformAuthProvider } from "@/features/platform";

export default function PlatformLayout({ children }: { children: ReactNode }) {
  return <PlatformAuthProvider>{children}</PlatformAuthProvider>;
}
