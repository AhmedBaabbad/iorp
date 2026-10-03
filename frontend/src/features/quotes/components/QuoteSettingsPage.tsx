"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getQuoteSettings, updateQuoteSettings } from "../api/quotes-api";
import type { QuoteSettings, QuoteTerm } from "../types";

// The usual headings of a quotation's terms; the bodies are the company's own policy.
const STANDARD_TERMS: { title_ar: string; title_en: string }[] = [
  { title_ar: "المواصفات الفنية", title_en: "Technical specification" },
  { title_ar: "مدة الصلاحية", title_en: "Validity" },
  { title_ar: "الأسعار", title_en: "Prices" },
  { title_ar: "التسليم", title_en: "Delivery" },
  { title_ar: "الدفع", title_en: "Payment" },
];

const emptyTerm = (title_ar = "", title_en = ""): QuoteTerm => ({ title_ar, title_en, body_ar: "", body_en: "", is_active: true });

/** The signature and the bilingual terms and conditions printed on every quotation. */
export function QuoteSettingsPage() {
  const t = useTranslations("commercial.quotes.settings");
  const messages = useTranslations("messages");
  const canUpdate = usePermission("commercial:quote_settings:update");
  const [settings, setSettings] = useState<QuoteSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getQuoteSettings().then(setSettings).catch((caught) => setError(getApiErrorMessage(caught, messages)));
  }, [messages]);

  const setTerm = (index: number, change: Partial<QuoteTerm>) =>
    setSettings((s) => s && { ...s, terms: s.terms.map((term, i) => (i === index ? { ...term, ...change } : term)) });
  const move = (index: number, by: number) => setSettings((s) => {
    if (!s) return s;
    const terms = [...s.terms];
    const [term] = terms.splice(index, 1);
    terms.splice(index + by, 0, term);
    return { ...s, terms };
  });
  const missingStandard = STANDARD_TERMS.filter((std) => !settings?.terms.some((term) => term.title_ar === std.title_ar));

  async function save() {
    if (!settings) return;
    setSaving(true); setError(null); setNotice(null);
    try {
      const terms = settings.terms.filter((term) => term.title_ar.trim() && term.body_ar.trim())
        .map((term) => ({ ...term, title_en: term.title_en?.trim() || null, body_en: term.body_en?.trim() || null }));
      setSettings(await updateQuoteSettings({ ...settings, terms }));
      setNotice(t("saved"));
    } catch (caught) {
      setError(getApiErrorMessage(caught, messages));
    } finally {
      setSaving(false);
    }
  }

  const disabled = !canUpdate || saving;
  return (
    <PageFrame title={t("title")} subtitle={t("subtitle")}
      action={<Link href="/quotes" style={sharedStyles.secondaryButton}>{t("backToQuotes")}</Link>}>
      {error ? <div style={sharedStyles.error} role="alert">{error}</div> : null}
      {notice ? <div role="status" style={{ ...sharedStyles.state, background: "var(--surface)" }}>{notice}</div> : null}
      {!settings && !error ? <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{messages("loading.default")}</div> : null}
      {settings ? (
        <div style={{ display: "grid", gap: "20px" }}>
          <section style={{ ...sharedStyles.state, background: "var(--surface)", textAlign: "start", display: "grid", gap: "14px" }}>
            <h2 style={{ margin: 0, fontSize: "18px" }}>{t("signature")}</h2>
            <p style={{ margin: 0, color: "var(--text-muted)" }}>{t("signatureHint")}</p>
            <div style={{ display: "grid", gap: "14px", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
              <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("signatureTitleAr")}</span>
                <input style={sharedStyles.input} dir="rtl" value={settings.signature_title_ar ?? ""} disabled={disabled} maxLength={255}
                  onChange={(e) => setSettings({ ...settings, signature_title_ar: e.target.value })} /></label>
              <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("signatureTitleEn")}</span>
                <input style={sharedStyles.input} dir="ltr" value={settings.signature_title_en ?? ""} disabled={disabled} maxLength={255}
                  onChange={(e) => setSettings({ ...settings, signature_title_en: e.target.value })} /></label>
            </div>
            <label style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <input type="checkbox" checked={settings.show_preparer_name} disabled={disabled}
                onChange={(e) => setSettings({ ...settings, show_preparer_name: e.target.checked })} />
              {t("showPreparer")}
            </label>
          </section>

          <section style={{ ...sharedStyles.state, background: "var(--surface)", textAlign: "start", display: "grid", gap: "14px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", justifyContent: "space-between", alignItems: "center" }}>
              <div><h2 style={{ margin: 0, fontSize: "18px" }}>{t("terms")}</h2>
                <p style={{ margin: "4px 0 0", color: "var(--text-muted)" }}>{t("termsHint")}</p></div>
              {canUpdate ? <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                {missingStandard.length ? <button type="button" style={sharedStyles.secondaryButton} disabled={disabled}
                  onClick={() => setSettings({ ...settings, terms: [...settings.terms, ...missingStandard.map((s) => emptyTerm(s.title_ar, s.title_en))] })}>
                  {t("addStandard")}</button> : null}
                <button type="button" style={sharedStyles.secondaryButton} disabled={disabled}
                  onClick={() => setSettings({ ...settings, terms: [...settings.terms, emptyTerm()] })}>{t("addTerm")}</button>
              </div> : null}
            </div>
            {!settings.terms.length ? <p style={{ margin: 0 }}>{t("noTerms")}</p> : null}
            {settings.terms.map((term, index) => (
              <fieldset key={index} style={{ border: "1px solid var(--border)", borderRadius: "8px", padding: "14px", display: "grid", gap: "12px", opacity: term.is_active ? 1 : 0.6 }}>
                <legend style={{ padding: "0 6px", fontWeight: 600 }}>{index + 1}. {term.title_ar || t("newTerm")}</legend>
                <div style={{ display: "grid", gap: "12px", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
                  <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("titleAr")} *</span>
                    <input style={sharedStyles.input} dir="rtl" value={term.title_ar} maxLength={120} disabled={disabled}
                      onChange={(e) => setTerm(index, { title_ar: e.target.value })} /></label>
                  <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("titleEn")}</span>
                    <input style={sharedStyles.input} dir="ltr" value={term.title_en ?? ""} maxLength={120} disabled={disabled}
                      onChange={(e) => setTerm(index, { title_en: e.target.value })} /></label>
                  <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("bodyAr")} *</span>
                    <textarea style={{ ...sharedStyles.textarea, minHeight: "80px" }} dir="rtl" value={term.body_ar} maxLength={2000} disabled={disabled}
                      onChange={(e) => setTerm(index, { body_ar: e.target.value })} /></label>
                  <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("bodyEn")}</span>
                    <textarea style={{ ...sharedStyles.textarea, minHeight: "80px" }} dir="ltr" value={term.body_en ?? ""} maxLength={2000} disabled={disabled}
                      onChange={(e) => setTerm(index, { body_en: e.target.value })} /></label>
                </div>
                {canUpdate ? <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                  <label style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                    <input type="checkbox" checked={term.is_active} disabled={disabled} onChange={(e) => setTerm(index, { is_active: e.target.checked })} />
                    {t("active")}
                  </label>
                  <button type="button" style={sharedStyles.secondaryButton} disabled={disabled || index === 0} aria-label={t("moveUp")} onClick={() => move(index, -1)}>↑</button>
                  <button type="button" style={sharedStyles.secondaryButton} disabled={disabled || index === settings.terms.length - 1} aria-label={t("moveDown")} onClick={() => move(index, 1)}>↓</button>
                  <button type="button" style={sharedStyles.secondaryButton} disabled={disabled}
                    onClick={() => setSettings({ ...settings, terms: settings.terms.filter((_, i) => i !== index) })}>{t("remove")}</button>
                </div> : null}
              </fieldset>
            ))}
          </section>

          {canUpdate ? <div><button type="button" style={sharedStyles.button} disabled={saving} onClick={() => void save()}>
            {saving ? messages("loading.saving") : t("save")}</button></div> : null}
        </div>
      ) : null}
    </PageFrame>
  );
}
