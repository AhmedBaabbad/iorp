"use client";
/**
 * How people read the organization's logs (ORG-AUDIT-002): every operation as a sentence in the screen's language, never
 * a raw code. An operation named "<record>.<verb>[.<list>]" reads from its exact words when the page has them, else from
 * the record's and the verb's words (logs.json), else a plain "an operation in the system". Details show as labelled
 * values — before → after — without ids or technical keys.
 */
import { useCallback } from "react";
import { useLocale, useTranslations } from "next-intl";

import { useFormatter } from "@/hooks/useFormatter";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ISO_TIME = /^\d{4}-\d{2}-\d{2}(T[\d:.]+(Z|[+-]\d{2}:?\d{2})?)?$/;
const HIDDEN = /(^id$|_id$|^performed_by$|_hash$|^jti|token)/;

type Translate = ReturnType<typeof useTranslations>;

/** The sentence of an operation; `exact` is the page's own words for it, when it has them. The same rule writes the
 * archive files (backend foundation/domain/log_words.py). */
export function useOperationText(exact?: Translate, exactPrefix = "actions") {
  const t = useTranslations("logs");
  return useCallback((raw: string | null | undefined, details?: unknown): string => {
    if (!raw) return t("unknownAction");
    let code = raw;
    const step = (details as { action?: unknown } | null)?.action;
    if (code === "production_order.status_changed" && typeof step === "string" && t.has(`verbs.${step}`)) code = `production_order.${step}`;
    if (exact && exact.has(`${exactPrefix}.${code}`)) return exact(`${exactPrefix}.${code}`);
    if (t.has(`exact.${code}`)) return t(`exact.${code}`);
    const [entity, verb, list] = code.replace(/^(tenant|platform)\./, "").split(".");
    const entityWords = entity && t.has(`entities.${entity}`) ? t(`entities.${entity}`) : null;
    const verbWords = verb && t.has(`verbs.${verb}`) ? t(`verbs.${verb}`) : null;
    if (!entityWords && !verbWords) return t("unknownAction");
    const values = { entity: entityWords ?? t("unknownEntity"), verb: verbWords ?? t("unknownVerb") };
    const text = list ? t("composedList", { ...values, list: t.has(`lists.${list}`) ? t(`lists.${list}`) : list.replaceAll("_", " ") })
      : t("composed", values);
    return text.replaceAll("لـ ", "ل");  // "تسجيل السبب الجذري لـ تقرير" reads "… لتقرير"
  }, [t, exact, exactPrefix]);
}

/** The words of a kind of record (user, purchase order…). */
export function useEntityText() {
  const t = useTranslations("logs");
  return useCallback((entity: string | null | undefined) => entity && t.has(`entities.${entity}`) ? t(`entities.${entity}`) : t("unknownEntity"), [t]);
}

type Row = { label: string; value: string };

/** The details of an entry as labelled values, in the screen's language. */
export function useDetailRows() {
  const t = useTranslations("logs");
  const locale = useLocale();
  const fmt = useFormatter();
  const label = useCallback((key: string) => t.has(`fields.${key}`) ? t(`fields.${key}`) : key.replaceAll("_", " "), [t]);
  const value = useCallback((key: string, raw: unknown, names?: Record<string, { ar: string; en: string }>): string => {
    if (raw === null || raw === undefined || raw === "") return t("empty");
    if (typeof raw === "boolean") return raw ? t("yes") : t("no");
    if (Array.isArray(raw)) return raw.map((v) => value(key, v, names)).join("، ");
    if (typeof raw === "object") return Object.entries(raw as Record<string, unknown>).filter(([k]) => !HIDDEN.test(k))
      .map(([k, v]) => `${label(k)}: ${value(k, v, names)}`).join(" · ");
    const text = String(raw);
    if (names?.[text]) return locale === "ar" ? names[text].ar : names[text].en;
    if (t.has(`values.${text}`)) return t(`values.${text}`);
    if (ISO_TIME.test(text)) return text.length > 10 ? fmt.dateTime(text) : fmt.date(text);
    return text;
  }, [t, locale, fmt, label]);

  return useCallback((details: unknown, names?: Record<string, { ar: string; en: string }>): Row[] => {
    if (details === null || details === undefined) return [];
    if (typeof details !== "object" || Array.isArray(details)) return [{ label: t("fields.field"), value: value("", details, names) }];
    const rows: Row[] = [];
    for (const [key, raw] of Object.entries(details as Record<string, unknown>)) {
      if (HIDDEN.test(key) || (typeof raw === "string" && UUID.test(raw))) continue;
      if (raw && typeof raw === "object" && !Array.isArray(raw) && ("before" in raw || "after" in raw)) {
        const change = raw as { before?: unknown; after?: unknown };
        rows.push({ label: label(key), value: t("beforeAfter", { before: value(key, change.before, names), after: value(key, change.after, names) }) });
      } else if (raw && typeof raw === "object" && !Array.isArray(raw) && (key === "changes" || key === "fields" || key === "previous")) {
        rows.push(...Object.entries(raw as Record<string, unknown>).filter(([k]) => !HIDDEN.test(k))
          .map(([k, v]) => ({ label: label(k), value: value(k, v, names) })));
      } else if (raw !== null && raw !== undefined && raw !== "") {
        rows.push({ label: label(key), value: value(key, raw, names) });
      }
    }
    return rows;
  }, [t, label, value]);
}

/** Details as a small definition list. */
export function DetailList({ rows }: { rows: Row[] }) {
  const t = useTranslations("logs");
  if (!rows.length) return <p style={{ margin: 0, color: "var(--text-muted)" }}>{t("noDetails")}</p>;
  return <dl style={{ display: "grid", gridTemplateColumns: "minmax(120px, max-content) 1fr", gap: "6px 16px", margin: 0 }}>
    {rows.map((r, i) => <div key={i} style={{ display: "contents" }}>
      <dt style={{ color: "var(--text-muted)", fontWeight: 700 }}>{r.label}</dt>
      <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{r.value}</dd>
    </div>)}
  </dl>;
}
