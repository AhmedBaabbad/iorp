"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { sharedStyles } from "@/styles/shared-styles";
import { validPercent } from "../discount";

// The unit dropdown is the shared one (all screens use the same catalogue and labels).
export { UnitSelect } from "@/components/forms/UnitSelect";

/** The line as printed on the quotation, in Arabic and English. Empty uses the product and its specification. */
export function LineDescriptionFields({ arabic, english, onChange, disabled }: {
  arabic: string; english: string; onChange: (field: "description_ar" | "description_en", value: string) => void; disabled?: boolean;
}) {
  const t = useTranslations("commercial.quotes.document");
  return (
    <details open={Boolean(arabic || english)}>
      <summary style={{ cursor: "pointer", color: "var(--accent-strong)" }}>{t("customDescription")}</summary>
      <p style={{ margin: "6px 0 10px", color: "var(--text-muted)", fontSize: "13px" }}>{t("customDescriptionHint")}</p>
    <div style={{ display: "grid", gap: "12px", gridTemplateColumns: "repeat(auto-fit, minmax(min(260px, 100%), 1fr))" }}>
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

/** A percentage put on every line at once; each line's own field can then be changed (or cleared) alone. */
export function DiscountAllField({ onApply, disabled }: { onApply: (percent: string) => void; disabled?: boolean }) {
  const t = useTranslations("commercial.quotes.discount");
  const [value, setValue] = useState("");
  const valid = value !== "" && validPercent(value);
  return (
    <div style={sharedStyles.field}>
      <span style={sharedStyles.label}>{t("allLines")}</span>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
        <input style={sharedStyles.input} type="number" min="0" max="100" step="0.01" value={value} disabled={disabled}
          aria-label={t("allLines")} placeholder="10" onChange={(event) => setValue(event.target.value)} />
        <button type="button" style={sharedStyles.secondaryButton} disabled={disabled || !valid} onClick={() => onApply(value)}>{t("apply")}</button>
      </div>
      <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "13px" }}>{t("allLinesHint")}</p>
    </div>
  );
}

/** One line's discount percentage and what it takes off the line. */
export function LineDiscountField({ value, amount, onChange, disabled }: {
  value: string; amount: number; onChange: (value: string) => void; disabled?: boolean;
}) {
  const t = useTranslations("commercial.quotes.discount");
  return (
    <label style={sharedStyles.field}>
      <span style={sharedStyles.label}>{t("line")}</span>
      <input style={sharedStyles.input} type="number" min="0" max="100" step="0.01" value={value} disabled={disabled}
        placeholder="0" onChange={(event) => onChange(event.target.value)} />
      {amount > 0 ? <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>{t("lineAmount", { amount: amount.toFixed(2) })}</span> : null}
    </label>
  );
}

/** "Attention" and "Subject" lines printed in the quotation's customer block. */
export function QuoteHeadingFields({ attention, subject, onChange, disabled }: {
  attention: string; subject: string; onChange: (field: "attention" | "subject", value: string) => void; disabled?: boolean;
}) {
  const t = useTranslations("commercial.quotes.document");
  return (
    <div style={{ display: "grid", gap: "18px", gridTemplateColumns: "repeat(auto-fit, minmax(min(220px, 100%), 1fr))" }}>
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
