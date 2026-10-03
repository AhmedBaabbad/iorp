"use client";

import { useTranslations } from "next-intl";
import { sharedStyles } from "@/styles/shared-styles";
import { QUOTE_UNIT_GROUPS, QUOTE_UNITS } from "../quote-units";

/** Unit of measure as a grouped dropdown. A unit saved before the list existed stays selectable as written. */
export function UnitSelect({ value, onChange, disabled }: { value: string; onChange: (value: string) => void; disabled?: boolean }) {
  const t = useTranslations("commercial.quoteUnits");
  const legacy = value && !QUOTE_UNITS.includes(value);
  return (
    <select style={sharedStyles.input} value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} required>
      <option value="">{t("choose")}</option>
      {legacy ? <option value={value}>{value}</option> : null}
      {(Object.keys(QUOTE_UNIT_GROUPS) as (keyof typeof QUOTE_UNIT_GROUPS)[]).map((group) => (
        <optgroup key={group} label={t(`groups.${group}`)}>
          {QUOTE_UNIT_GROUPS[group].map((code) => <option key={code} value={code}>{t(`units.${code}`)}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

/** The line as printed on the quotation, in Arabic and English. Empty uses the product and its specification. */
export function LineDescriptionFields({ arabic, english, onChange, disabled }: {
  arabic: string; english: string; onChange: (field: "description_ar" | "description_en", value: string) => void; disabled?: boolean;
}) {
  const t = useTranslations("commercial.quotes.document");
  return (
    <details open={Boolean(arabic || english)}>
      <summary style={{ cursor: "pointer", color: "var(--accent-strong)" }}>{t("customDescription")}</summary>
      <p style={{ margin: "6px 0 10px", color: "var(--text-muted)", fontSize: "13px" }}>{t("customDescriptionHint")}</p>
    <div style={{ display: "grid", gap: "12px", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
      <label style={sharedStyles.field}>
        <span style={sharedStyles.label}>{t("descriptionAr")}</span>
        <textarea style={{ ...sharedStyles.textarea, minHeight: "64px" }} dir="rtl" lang="ar" value={arabic} maxLength={1000}
          onChange={(event) => onChange("description_ar", event.target.value)} disabled={disabled} placeholder={t("descriptionArHint")} />
      </label>
      <label style={sharedStyles.field}>
        <span style={sharedStyles.label}>{t("descriptionEn")}</span>
        <textarea style={{ ...sharedStyles.textarea, minHeight: "64px" }} dir="ltr" lang="en" value={english} maxLength={1000}
          onChange={(event) => onChange("description_en", event.target.value)} disabled={disabled} placeholder={t("descriptionEnHint")} />
      </label>
    </div>
    </details>
  );
}

/** "Attention" and "Subject" lines printed in the quotation's customer block. */
export function QuoteHeadingFields({ attention, subject, onChange, disabled }: {
  attention: string; subject: string; onChange: (field: "attention" | "subject", value: string) => void; disabled?: boolean;
}) {
  const t = useTranslations("commercial.quotes.document");
  return (
    <div style={{ display: "grid", gap: "18px", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
      <label style={sharedStyles.field}>
        <span style={sharedStyles.label}>{t("attention")}</span>
        <input style={sharedStyles.input} value={attention} maxLength={255} placeholder={t("attentionHint")}
          onChange={(event) => onChange("attention", event.target.value)} disabled={disabled} />
      </label>
      <label style={sharedStyles.field}>
        <span style={sharedStyles.label}>{t("subject")}</span>
        <input style={sharedStyles.input} value={subject} maxLength={255} placeholder={t("subjectHint")}
          onChange={(event) => onChange("subject", event.target.value)} disabled={disabled} />
      </label>
    </div>
  );
}
