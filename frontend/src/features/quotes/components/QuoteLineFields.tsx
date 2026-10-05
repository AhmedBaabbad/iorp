"use client";

import { useTranslations } from "next-intl";
import { sharedStyles } from "@/styles/shared-styles";

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
