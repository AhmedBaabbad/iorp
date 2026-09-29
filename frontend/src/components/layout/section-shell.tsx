import type { CSSProperties, ReactNode } from "react";

type SectionShellProps = {
  titleId: string;
  title: string;
  subtitle: string;
  children: ReactNode;
};

const styles: Record<string, CSSProperties> = {
  section: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
    marginTop: "24px",
    overflow: "hidden",
  },
  header: {
    borderBottom: "1px solid var(--border)",
    padding: "20px 24px",
  },
  title: {
    fontSize: "22px",
    margin: 0,
  },
  subtitle: {
    color: "var(--text-muted)",
    lineHeight: 1.5,
    margin: "6px 0 0",
  },
  body: {
    display: "grid",
    gap: "20px",
    padding: "24px",
  },
};

export function SectionShell({ titleId, title, subtitle, children }: SectionShellProps) {
  return (
    <section style={styles.section} aria-labelledby={titleId}>
      <header style={styles.header}>
        <h2 id={titleId} style={styles.title}>
          {title}
        </h2>
        <p style={styles.subtitle}>{subtitle}</p>
      </header>
      <div style={styles.body}>{children}</div>
    </section>
  );
}
