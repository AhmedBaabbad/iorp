"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { sharedStyles } from "@/styles/shared-styles";

/**
 * Search and a status filter above a paged list (ARCH-PAGE-001). Typing searches the server after a short pause; a new
 * search or filter goes back to page 1 (the caller's useListQuery does that).
 */
export function ListToolbar({ search, onSearch, searchHint, status, onStatus, statuses, statusLabel, onClear }: {
  search: string; onSearch: (value: string) => void; searchHint: string;
  status?: string; onStatus?: (value: string) => void; statuses?: { value: string; label: string }[]; statusLabel?: string;
  onClear: () => void;
}) {
  const t = useTranslations("common.listFilters");
  const [text, setText] = useState(search);
  useEffect(() => { setText(search); }, [search]);
  useEffect(() => {
    if (text.trim() === search) return;
    const timer = setTimeout(() => onSearch(text.trim()), 350);
    return () => clearTimeout(timer);
  }, [text]); // eslint-disable-line react-hooks/exhaustive-deps
  const filtered = Boolean(search || status);
  return (
    <section aria-label={t("label")} style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end", marginBottom: 16, padding: "14px 16px",
      background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: 8 }}>
      <label style={{ ...sharedStyles.field, flex: "2 1 260px" }}>
        <span style={sharedStyles.label}>{t("search")}</span>
        <input type="search" style={sharedStyles.input} value={text} placeholder={searchHint} onChange={(e) => setText(e.target.value)} />
      </label>
      {statuses && onStatus ? (
        <label style={{ ...sharedStyles.field, flex: "1 1 180px" }}>
          <span style={sharedStyles.label}>{statusLabel}</span>
          <select style={sharedStyles.input} value={status ?? ""} onChange={(e) => onStatus(e.target.value)}>
            <option value="">{t("all")}</option>
            {statuses.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
      ) : null}
      {filtered ? <button type="button" style={sharedStyles.secondaryButton} onClick={() => { setText(""); onClear(); }}>{t("clear")}</button> : null}
    </section>
  );
}
