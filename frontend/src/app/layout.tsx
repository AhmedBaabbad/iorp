import type { ReactNode } from "react";

import { AuthProvider } from "@/features/auth";

export const metadata = {
  title: "IORP",
  description: "Industrial Operations & Relationship Platform",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0 }}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
