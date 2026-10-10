"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState, type FormEvent } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { MD } from "@/lib/masterdata-permissions";
import { getBusinessSettings, updateBusinessSettings } from "../api";
import { refreshCatalog } from "../catalog";
import { masterdataErrorMessage } from "../masterdata-errors";
import type { BusinessSettings } from "../types";

const RATE = /^\d{1,3}(\.\d{1,2})?$/;

// «الإعدادات العامة»: the VAT rate and the default currency of new quotations and purchase orders.
export function GeneralSettings() {
  const t = useTranslations("masterdata.settings");
  const errors = useTranslations("masterdata.errors");
  const messages = useTranslations("messages");
  const currencies = useTranslations("common.currencies");
  const canEdit = usePermission(MD.SETTINGS_UPDATE);
  const [v, setV] = useState<BusinessSettings | null>(null);
  const [rate, setRate] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    getBusinessSettings().then(x => { setV(x); setRate(String(Number(x.vat_rate))); }).catch(e => setError(masterdataErrorMessage(e, errors)));
  }, [errors]);
  const valid = RATE.test(rate.trim()) && Number(rate) <= 100;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!v || !valid || busy) return;
    setBusy(true); setMessage(""); setError("");
    try {
      const saved = await updateBusinessSettings({ vat_rate: rate.trim(), default_currency: v.default_currency });
      setV(saved); setRate(String(Number(saved.vat_rate))); refreshCatalog(); setMessage(t("saved"));
    } catch (e) { setError(masterdataErrorMessage(e, errors)); } finally { setBusy(false); }
  }
  return <PageFrame title={t("title")} subtitle={t("subtitle")}>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {!v && !error && <p className={s.muted}>{messages("loading.default")}</p>}
    {v && <form className={s.panel} onSubmit={submit} aria-label={t("title")}>
      <fieldset disabled={!canEdit || busy} style={{ border: 0, padding: 0, margin: 0, display: "grid", gap: 12 }}>
        <div className={s.grid}>
          <label className={s.field}>{t("vatRate")}<input inputMode="decimal" dir="ltr" required value={rate} onChange={e => setRate(e.target.value)} />
            <span className={s.muted}>{t("vatHint")}</span></label>
          <label className={s.field}>{t("currency")}
            <select value={v.default_currency} onChange={e => setV({ ...v, default_currency: e.target.value as BusinessSettings["default_currency"] })}>
              {v.currencies.map(c => <option key={c} value={c}>{currencies.has(c) ? currencies(c) : c} ({c})</option>)}</select>
            <span className={s.muted}>{t("currencyHint")}</span></label>
        </div>
        {!valid && <p className={s.error} style={{ margin: 0 }}>{t("vatInvalid")}</p>}
        <p className={s.muted} style={{ margin: 0 }}>{t("note")}</p>
        {canEdit && <div className={s.actions}><button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy}>{t("save")}</button>
          {message && <span role="status" className={s.muted}>{message}</span>}</div>}
      </fieldset>
    </form>}
  </PageFrame>;
}
