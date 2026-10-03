"use client";

import { useTranslations } from "next-intl";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import type { DowntimeSummary } from "../types";
import { DowntimeCategoryBadge, DowntimeTypeBadge } from "./DowntimeBadges";

// Report figures for the filtered stops: planned vs. availability loss, open stops, MTTR, by cause and machine.
export function DowntimeSummaryCards({ summary, showMachines = true }: { summary: DowntimeSummary; showMachines?: boolean }) {
  const t = useTranslations("production.downtimeEvents.summary");
  const fmt = useFormatter();
  const minutes = (value: string | null) => (value === null ? "—" : fmt.duration(Math.round(Number(value))));
  const cards: [string, string][] = [
    ["total", minutes(summary.total_minutes)], ["loss", minutes(summary.unplanned_minutes)], ["planned", minutes(summary.planned_minutes)],
    ["count", String(summary.count)], ["mttr", minutes(summary.mttr_minutes)],
    ["open", summary.open_count ? t("openValue", { count: String(summary.open_count), minutes: minutes(summary.open_minutes_so_far) }) : "0"],
  ];
  return <div>
    <dl className={s.grid} style={{ margin: "0 0 12px" }} aria-label={t("label")}>
      {cards.map(([key, value]) => <div key={key} className={s.panel} style={{ margin: 0, padding: 14 }}>
        <dt className={s.muted}>{t(key)}</dt><dd style={{ margin: "6px 0 0", fontSize: 20, fontWeight: 700 }}>{value}</dd>
      </div>)}
    </dl>
    <p className={s.muted}>{t("hint")}</p>
    {summary.by_category.length > 0 && <div className={s.tableWrap}><table className={s.table} aria-label={t("byCategory")}>
      <thead><tr><th>{t("category")}</th><th>{t("type")}</th><th>{t("stops")}</th><th>{t("minutes")}</th></tr></thead>
      <tbody>{summary.by_category.map(row => <tr key={row.category}>
        <td><DowntimeCategoryBadge category={row.category} /></td><td><DowntimeTypeBadge planned={row.planned} /></td><td>{row.count}</td><td>{minutes(row.minutes)}</td>
      </tr>)}</tbody>
    </table></div>}
    {showMachines && summary.by_work_center.length > 1 && <div className={s.tableWrap} style={{ marginTop: 12 }}><table className={s.table} aria-label={t("byMachine")}>
      <thead><tr><th>{t("machine")}</th><th>{t("stops")}</th><th>{t("minutes")}</th><th>{t("lossMinutes")}</th></tr></thead>
      <tbody>{summary.by_work_center.map(row => <tr key={row.work_center_id}>
        <td>{row.work_center_name ?? "—"}</td><td>{row.count}</td><td>{minutes(row.minutes)}</td><td>{minutes(row.unplanned_minutes)}</td>
      </tr>)}</tbody>
    </table></div>}
  </div>;
}
