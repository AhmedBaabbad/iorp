"use client";
/**
 * The activity log's archive (ORG-AUDIT-003): the months past their 12-month retention. Each is downloaded as a file built
 * on request (never stored), then deleted once the person confirms they kept it; a month nobody archives is deleted
 * automatically on its date. Shown to holders of foundation:activity_log:archive.
 */
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { useLocale, useTranslations } from "next-intl";

import { useNotify } from "@/components/notify/Notifications";
import { useFormatter } from "@/hooks/useFormatter";
import { apiClient } from "@/lib/api-client";
import { downloadFile } from "@/lib/download";
import { sharedStyles } from "@/styles/shared-styles";

type Month = { month: string; rows: number; due_on: string; delete_on: string; downloaded_at: string | null; downloaded_by_name: string | null };
const ROOT = "/admin/activity-log/archive";
const cell: CSSProperties = { padding: "10px 12px", verticalAlign: "middle", textAlign: "start" };

/** "2025-09" in the reader's words ("سبتمبر 2025"). */
function useMonthName() {
  const locale = useLocale();
  return useCallback((month: string) => {
    const [y, m] = month.split("-").map(Number);
    return new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(y, m - 1, 1)));
  }, [locale]);
}

export function ActivityArchive() {
  const t = useTranslations("tenantActivity");
  const notify = useNotify();
  const fmt = useFormatter();
  const locale = useLocale();
  const monthName = useMonthName();
  const [months, setMonths] = useState<Month[] | null>(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => { apiClient<Month[]>(ROOT).then(setMonths).catch(() => setMonths([])); }, []);
  useEffect(load, [load]);

  async function download(m: Month) {
    setBusy(m.month);
    try { await downloadFile(`${ROOT}/${m.month}/download?locale=${locale}`, `activity-${m.month}.zip`); load(); }
    catch { notify.error(t("downloadFailed")); } finally { setBusy(""); }
  }
  async function remove(m: Month) {
    if (!window.confirm(t("confirmDelete", { month: monthName(m.month) }))) return;
    setBusy(m.month);
    try {
      const done = await apiClient<{ rows: number }>(`${ROOT}/${m.month}/delete`, { method: "POST", notify: false });
      notify.success(t("deleted", { rows: done.rows, month: monthName(m.month) }));
      load();
    } catch { notify.error(t("deleteFailed")); } finally { setBusy(""); }
  }

  return <section id="archive" style={{ background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: 12, padding: 18, marginTop: 16 }}>
    <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>{t("archiveTitle")}</h2>
    <p style={{ margin: "0 0 12px", color: "var(--text-muted)" }}>{t("archiveHint")}</p>
    {!months ? null : !months.length ? <p style={{ margin: 0 }}>{t("archiveEmpty")}</p> : <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr>{(["month", "rows", "deleteOn"] as const).map((k) => <th key={k} style={{ ...cell, color: "var(--text-muted)", fontSize: 13 }}>{t(k)}</th>)}<th style={cell} /></tr></thead>
        <tbody>{months.map((m) => <tr key={m.month} style={{ borderTop: "1px solid var(--border)" }}>
          <td style={{ ...cell, fontWeight: 700 }}>{monthName(m.month)}</td>
          <td style={cell}>{m.rows}</td>
          <td style={{ ...cell, color: "var(--danger)" }}>{fmt.date(m.delete_on)}</td>
          <td style={{ ...cell, display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <button type="button" style={sharedStyles.secondaryButton} disabled={busy === m.month} onClick={() => void download(m)}>{t("download")}</button>
            {m.downloaded_at && <>
              <button type="button" style={sharedStyles.button} disabled={busy === m.month} onClick={() => void remove(m)}>{t("delete")}</button>
              <span style={{ color: "var(--text-muted)", fontSize: 12 }}>{t("downloaded", { name: m.downloaded_by_name ?? "", date: fmt.dateTime(m.downloaded_at) })}</span>
            </>}
          </td>
        </tr>)}</tbody>
      </table></div>}
  </section>;
}
