"use client";
import { specificationRows } from "@/lib/spec-value";

import { useLocale, useTranslations } from "next-intl";

import { useProducts } from "@/features/masterdata";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import s from "@/features/production-demands/demands.module.css";

type Translate = ReturnType<typeof useTranslations>;

/** A refusal of the quotation or sales order lifecycle (SALES-001), in the screen's language. The server sends
 * "CODE" or "CODE:value" (the order number already made from a quotation, the property that is not valid). */
export function salesErrorMessage(error: unknown, t: Translate, messages: Translate) {
  const detail = (error as { details?: { detail?: unknown } } | null)?.details?.detail;
  if (typeof detail === "string") {
    const [code, ...rest] = detail.split(":");
    if (t.has(code)) return t(code, { value: rest.join(":") });
  }
  return getApiErrorMessage(error, messages);
}

export type HistoryEntry = {
  action: string;
  to_status: string;
  revision: number;
  reason: string | null;
  actor_name: string | null;
  created_at: string;
};

/** Every step of a quotation's or a sales order's life, oldest first: who, when, the revision, and the reason. */
export function StatusHistory({ entries }: { entries: HistoryEntry[] }) {
  const t = useTranslations("commercial.history");
  const fmt = useFormatter();
  return (
    <section className={s.panel} aria-label={t("title")}>
      <h2 style={{ marginTop: 0 }}>{t("title")}</h2>
      {entries.length === 0 ? <p className={s.muted}>{t("empty")}</p> : (
        <ol className={s.timeline}>
          {entries.map((e, i) => (
            <li key={`${e.created_at}-${i}`}>
              <strong>{t.has(`events.${e.action}`) ? t(`events.${e.action}`) : e.action}</strong>
              <span className={s.muted}>
                {e.actor_name ?? "—"} · {fmt.dateTime(e.created_at)} · {t("revision", { number: e.revision })}
              </span>
              {e.reason && <span style={{ whiteSpace: "pre-wrap" }}>{e.reason}</span>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/** A line's specification by its product's template: the property's name, the value with its unit, a choice's label. */
export function SpecList({ productKey, spec }: { productKey: string; spec: Record<string, unknown> | null }) {
  const locale = useLocale();
  const units = useTranslations("common.units.units");
  const product = useProducts()?.find((p) => p.key === productKey);
  const rows=specificationRows(spec,{properties:product?.properties,locale,unitLabel:unit=>units.has(unit)?units(unit):unit});
  if(!rows.length)return null;
  return <ul style={{margin:"6px 0 0",paddingInlineStart:18}} className={s.muted}>
    {rows.map(row=><li key={row.key}><strong>{row.name}</strong>: <bdi dir={row.range?"ltr":"auto"}>{row.valueWithUnit}</bdi></li>)}
  </ul>;
}
