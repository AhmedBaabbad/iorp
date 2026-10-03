"use client";

import { useTranslations } from "next-intl";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import type { HistoryEntry } from "../types";

// The lifecycle of a check or rejection, oldest first; statusLabel names a status in the record's own enum.
export function QualityHistory({ entries, statusLabel }: { entries: HistoryEntry[]; statusLabel: (status: string) => string }) {
  const t = useTranslations("quality.history");
  const fmt = useFormatter();
  return <section className={s.panel} aria-label={t("title")}>
    <h2 style={{ marginTop: 0 }}>{t("title")}</h2>
    {entries.length === 0 ? <p className={s.muted} style={{ margin: 0 }}>{t("empty")}</p> : <ol className={s.timeline}>
      {entries.map((h, i) => <li key={`${h.at}-${i}`}>
        <strong>{t.has(`actions.${h.action}`) ? t(`actions.${h.action}`) : h.action}
          {h.from_status && h.from_status !== h.to_status && <span className={s.muted}> — {t("transition", { from: statusLabel(h.from_status), to: statusLabel(h.to_status) })}</span>}
        </strong>
        <span className={s.muted}>{h.actor_name ?? "—"} · {fmt.dateTime(h.at)}</span>
        {h.reason && <span style={{ whiteSpace: "pre-wrap" }}>{h.reason}</span>}
      </li>)}
    </ol>}
  </section>;
}
