"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getQuoteSettings, updateQuoteSettings } from "../api/quotes-api";
import type { DocumentLanguage, QuoteSettings, QuoteTerm } from "../types";

// The usual headings of a quotation's terms; the bodies are the company's own policy.
const STANDARD_TERMS: { title_ar: string; title_en: string }[] = [
  { title_ar: "المواصفات الفنية", title_en: "Technical specification" },
  { title_ar: "مدة الصلاحية", title_en: "Validity" },
  { title_ar: "الأسعار", title_en: "Prices" },
  { title_ar: "التسليم", title_en: "Delivery" },
  { title_ar: "الدفع", title_en: "Payment" },
];

const emptyTerm = (title_ar = "", title_en = ""): QuoteTerm => ({ title_ar, title_en, body_ar: "", body_en: "", is_active: true });
const filled = (value: string | null | undefined) => Boolean(value?.trim());
const clean = (value: string | null | undefined) => value?.trim() || null;

/**
 * The language quotations are printed in, and the signature and terms written in it. Only the chosen language's fields
 * are shown; what was written in the other one is kept, never printed or lost.
 */
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

  const lang: DocumentLanguage = settings?.document_language ?? "ar";
  const dir = lang === "ar" ? "rtl" : "ltr";
  const title = `title_${lang}` as const;
  const body = `body_${lang}` as const;
  const signature = `signature_title_${lang}` as const;
  const setTerm = (index: number, change: Partial<QuoteTerm>) =>
    setSettings((s) => s && { ...s, terms: s.terms.map((term, i) => (i === index ? { ...term, ...change } : term)) });
  const move = (index: number, by: number) => setSettings((s) => {
    if (!s) return s;
    const terms = [...s.terms];
    const [term] = terms.splice(index, 1);
    terms.splice(index + by, 0, term);
    return { ...s, terms };
  });
  const missingStandard = STANDARD_TERMS.filter((std) => !settings?.terms.some((term) => term.title_ar === std.title_ar || term.title_en === std.title_en));

  async function save() {
    if (!settings) return;
    setSaving(true); setError(null); setNotice(null);
    try {
      // A term needs a title and a text in at least one language; empty new terms are dropped.
      const terms = settings.terms.map((term) => ({ ...term, title_ar: clean(term.title_ar), title_en: clean(term.title_en), body_ar: clean(term.body_ar),
        body_en: clean(term.body_en) })).filter((term) => (term.title_ar && term.body_ar) || (term.title_en && term.body_en));
      setSettings(await updateQuoteSettings({ ...settings, terms }));
      setNotice(t("saved"));
    } catch (caught) {
      setError(getApiErrorMessage(caught, messages));
    } finally {
      setSaving(false);
    }
  }

  const disabled = !canUpdate || saving;
  const panel = { ...sharedStyles.state, background: "var(--surface)", textAlign: "start" as const, display: "grid", gap: "14px" };
  return (
    <PageFrame title={t("title")} subtitle={t("subtitle")}
      action={<Link href="/quotes" style={sharedStyles.secondaryButton}>{t("backToQuotes")}</Link>}>
      {error ? <div style={sharedStyles.error} role="alert">{error}</div> : null}
      {notice ? <div role="status" style={{ ...sharedStyles.state, background: "var(--surface)" }}>{notice}</div> : null}
      {!settings && !error ? <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{messages("loading.default")}</div> : null}
      {settings ? (
        <div style={{ display: "grid", gap: "20px" }}>
          <section style={panel} aria-label={t("language")}>
            <h2 style={{ margin: 0, fontSize: "18px" }}>{t("language")}</h2>
            <p style={{ margin: 0, color: "var(--text-muted)" }}>{t("languageHint")}</p>
            <div role="radiogroup" aria-label={t("language")} style={{ display: "flex", gap: "18px", flexWrap: "wrap" }}>
              {(["ar", "en"] as const).map((option) => (
                <label key={option} style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                  <input type="radio" name="document_language" checked={lang === option} disabled={disabled}
                    onChange={() => setSettings({ ...settings, document_language: option })} />
                  {t(`languages.${option}`)}
                </label>
              ))}
            </div>
          </section>

          <section style={panel}>
            <h2 style={{ margin: 0, fontSize: "18px" }}>{t("signature")}</h2>
            <p style={{ margin: 0, color: "var(--text-muted)" }}>{t("signatureHint")}</p>
            <label style={{ ...sharedStyles.field, maxWidth: "420px" }}><span style={sharedStyles.label}>{t("signatureTitle")}</span>
              <input style={sharedStyles.input} dir={dir} value={settings[signature] ?? ""} disabled={disabled} maxLength={255}
                onChange={(e) => setSettings({ ...settings, [signature]: e.target.value })} /></label>
            <label style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <input type="checkbox" checked={settings.show_preparer_name} disabled={disabled}
                onChange={(e) => setSettings({ ...settings, show_preparer_name: e.target.checked })} />
              {t("showPreparer")}
            </label>
          </section>

          <section style={panel}>
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
            {settings.terms.map((term, index) => {
              const written = filled(term[title]) && filled(term[body]);
              return (
                <fieldset key={index} style={{ border: "1px solid var(--border)", borderRadius: "8px", padding: "14px", display: "grid", gap: "12px", opacity: term.is_active ? 1 : 0.6 }}>
                  <legend style={{ padding: "0 6px", fontWeight: 600 }}>{index + 1}. {term[title] || t("newTerm")}</legend>
                  {!written && term.is_active ? <p role="status" style={{ margin: 0, color: "var(--danger)" }}>{t("notWritten")}</p> : null}
                  <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("termTitle")}</span>
                    <input style={sharedStyles.input} dir={dir} value={term[title] ?? ""} maxLength={120} disabled={disabled}
                      onChange={(e) => setTerm(index, { [title]: e.target.value })} /></label>
                  <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("termBody")}</span>
                    <textarea style={{ ...sharedStyles.textarea, minHeight: "80px" }} dir={dir} value={term[body] ?? ""} maxLength={2000} disabled={disabled}
                      onChange={(e) => setTerm(index, { [body]: e.target.value })} /></label>
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
              );
            })}
          </section>

          {canUpdate ? <div><button type="button" style={sharedStyles.button} disabled={saving} onClick={() => void save()}>
            {saving ? messages("loading.saving") : t("save")}</button></div> : null}
        </div>
      ) : null}
    </PageFrame>
  );
}
