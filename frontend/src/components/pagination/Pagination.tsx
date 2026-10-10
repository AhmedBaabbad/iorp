"use client";

import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";

import { PAGE_SIZES, pageNumbers } from "@/lib/pagination";

const styles: Record<string, CSSProperties> = {
  bar: { display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "14px 16px",
    borderTop: "1px solid var(--border)" },
  group: { display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 },
  button: { minWidth: 36, padding: "7px 10px", border: "1px solid var(--border-strong)", borderRadius: 6, background: "var(--surface)",
    color: "var(--text)", cursor: "pointer", font: "inherit" },
  current: { background: "var(--accent-strong)", borderColor: "var(--accent-strong)", color: "var(--on-accent)", fontWeight: 700 },
  muted: { color: "var(--text-muted)", fontSize: 14 },
  select: { padding: "6px 8px", border: "1px solid var(--border-strong)", borderRadius: 6, background: "var(--surface)", color: "var(--text)", font: "inherit" },
};

/**
 * The bar under every paged list: "Showing 51–100 of 340", the pages (first, last and those around the current one), and
 * how many rows a page shows. The rows themselves come from the server one page at a time.
 */
export function Pagination({ page, pageSize, total, pages, onPage, onPageSize, disabled }: {
  page: number; pageSize: number; total: number; pages: number; onPage: (page: number) => void; onPageSize?: (size: number) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("common.pagination");
  if (total === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <nav style={styles.bar} aria-label={t("label")}>
      <span style={styles.muted} role="status">{t("showing", { from, to, total })}</span>
      <span style={styles.group}>
        <button type="button" style={styles.button} disabled={disabled || page <= 1} onClick={() => onPage(page - 1)}>{t("previous")}</button>
        {pageNumbers(page, pages).map((n, i) => n === "gap"
          ? <span key={`gap-${i}`} style={styles.muted} aria-hidden="true">…</span>
          : <button key={n} type="button" style={n === page ? { ...styles.button, ...styles.current } : styles.button} disabled={disabled}
              aria-current={n === page ? "page" : undefined} aria-label={t("page", { page: n })} onClick={() => n !== page && onPage(n)}>{n}</button>)}
        <button type="button" style={styles.button} disabled={disabled || page >= pages} onClick={() => onPage(page + 1)}>{t("next")}</button>
      </span>
      {onPageSize && (
        <label style={styles.group}>
          <span style={styles.muted}>{t("perPage")}</span>
          <select style={styles.select} value={pageSize} disabled={disabled} onChange={(e) => onPageSize(Number(e.target.value))}>
            {PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
          </select>
        </label>
      )}
    </nav>
  );
}
