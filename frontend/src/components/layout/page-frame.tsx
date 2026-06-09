"use client";

import type { CSSProperties, ReactNode } from "react";
import { useRouter } from "next/navigation";

import { ProtectedRoute, useAuth } from "@/features/auth";

type PageFrameProps = {
  title: string;
  subtitle?: string;
  section?: string;
  action?: ReactNode;
  children: ReactNode;
};

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: "#f6f7f9",
    color: "#1f2933",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    padding: "32px",
  },
  shell: {
    maxWidth: "1120px",
    margin: "0 auto",
  },
  topBar: {
    display: "flex",
    justifyContent: "flex-end",
    marginBottom: "16px",
  },
  signOut: {
    background: "none",
    border: "none",
    color: "#52606d",
    cursor: "pointer",
    fontSize: "14px",
    padding: "4px 0",
  },
  header: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: "16px",
    marginBottom: "24px",
  },
  eyebrow: {
    margin: "0 0 8px",
    color: "#52606d",
    fontSize: "14px",
    fontWeight: 700,
  },
  title: {
    margin: 0,
    fontSize: "30px",
    lineHeight: 1.2,
  },
  subtitle: {
    margin: "8px 0 0",
    color: "#52606d",
    lineHeight: 1.5,
  },
};

export function PageFrame({ title, subtitle, section, action, children }: PageFrameProps) {
  const { logout } = useAuth();
  const router = useRouter();

  function handleSignOut() {
    logout();
    router.replace("/login");
  }

  return (
    <ProtectedRoute>
      <main style={styles.page}>
        <div style={styles.shell}>
          <div style={styles.topBar}>
            <button style={styles.signOut} type="button" onClick={handleSignOut}>
              Sign out
            </button>
          </div>
          <header style={styles.header}>
            <div>
              <p style={styles.eyebrow}>{section ?? "Commercial"}</p>
              <h1 style={styles.title}>{title}</h1>
              {subtitle ? <p style={styles.subtitle}>{subtitle}</p> : null}
            </div>
            {action}
          </header>
          {children}
        </div>
      </main>
    </ProtectedRoute>
  );
}
