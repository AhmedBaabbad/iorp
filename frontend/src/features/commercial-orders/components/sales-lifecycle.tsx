"use client";

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
  const entries = Object.entries(spec ?? {}).filter(([, v]) => v !== null && v !== "");
  if (entries.length === 0) return null;
  const ordered = product
    ? [...entries].sort(([a], [b]) => indexOf(product.properties, a) - indexOf(product.properties, b))
    : entries;
  return (
    <ul style={{ margin: "6px 0 0", paddingInlineStart: 18 }} className={s.muted}>
      {ordered.map(([key, raw]) => {
        const prop = product?.properties.find((p) => p.key === key);
        const name = prop ? (locale === "ar" ? prop.name_ar : prop.name_en) : key;
        const option = prop?.options?.find((o) => o.value === raw);
        const value = option ? (locale === "ar" ? option.label_ar : option.label_en)
          : typeof raw === "object" ? JSON.stringify(raw) : String(raw);
        const unit = prop?.unit ? ` ${units.has(prop.unit) ? units(prop.unit) : prop.unit}` : "";
        return <li key={key}><strong>{name}</strong>: <bdi>{value}{unit}</bdi></li>;
      })}
    </ul>
  );
}

function indexOf(properties: { key: string }[], key: string) {
  const i = properties.findIndex((p) => p.key === key);
  return i === -1 ? properties.length : i;
}
