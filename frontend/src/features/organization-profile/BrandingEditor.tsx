"use client";
import { useEffect, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { useAuth } from '@/features/auth';
import { apiClient } from '@/lib/api-client';
import s from '@/features/reports/reports.module.css';

const FIELDS = ['legal_name_ar', 'legal_name_en', 'trade_name_ar', 'trade_name_en', 'descriptor_ar', 'descriptor_en',
  'commercial_registration_no', 'unified_number', 'vat_number', 'address_ar', 'address_en',
  'city', 'country', 'postal_code', 'phone', 'email', 'website', 'primary_color', 'report_footer_note_ar', 'report_footer_note_en'] as const;
// Saudi formats, checked again by the server: CR 10 digits, Unified No. 10 digits from 7, VAT 15 digits from 3 to 3.
const PATTERNS: Partial<Record<(typeof FIELDS)[number], string>> = {
  commercial_registration_no: '\\d{10}', unified_number: '7\\d{9}', vat_number: '3\\d{13}3',
};
const LOGO_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const MAX_LOGO = 2 * 1024 * 1024;
const DEFAULT_ACCENT = '#24556b'; // theme-exempt: the printed report's default accent (data), not a screen color

// Company bank accounts printed in the quotation footer; several are allowed, inactive ones are kept but not printed.
type BankAccount = { bank_name_ar: string; bank_name_en: string | null; account_name: string | null; account_number: string | null;
  iban: string; swift_code: string | null; is_active: boolean };
const BANK_FIELDS = ['bank_name_ar', 'bank_name_en', 'account_name', 'account_number', 'iban', 'swift_code'] as const;
const emptyBank = (): BankAccount => ({ bank_name_ar: '', bank_name_en: '', account_name: '', account_number: '', iban: '', swift_code: '', is_active: true });

// Company identity printed in report headers and footers, with a live preview.
export function BrandingEditor({ revision }: { revision?: string }) {
  const t = useTranslations('organization.branding');
  const ar = useLocale() === 'ar';
  const { hasPermission } = useAuth();
  const [data, setData] = useState<Record<string, string | null>>({});
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [error, setError] = useState(''); const [saved, setSaved] = useState(false); const [busy, setBusy] = useState(false);
  const canRead = hasPermission('organization:branding:read'), canWrite = hasPermission('organization:branding:update');

  const load = (value: Record<string, unknown>) => { setData(value as Record<string, string | null>); setBanks((value.bank_accounts as BankAccount[] | undefined) ?? []); };
  useEffect(() => { if (canRead) apiClient<Record<string, unknown>>('/organization/branding').then(load).catch(() => setError(t('loadError'))); }, [canRead, revision, t]);
  if (!canRead) return null;

  async function save() {
    setBusy(true); setSaved(false); setError('');
    const bank_accounts = banks.filter(b => b.bank_name_ar.trim() || b.iban.trim())
      .map(b => Object.fromEntries(Object.entries(b).map(([k, v]) => [k, typeof v === 'string' ? v.trim() || null : v])));
    try { load(await apiClient('/organization/branding', { method: 'PUT', body: { ...Object.fromEntries(FIELDS.map(k => [k, data[k] || null])), bank_accounts } })); setSaved(true); }
    catch (caught) { setError((caught as { status?: number })?.status === 422 ? t('invalidValues') : t('saveError')); } finally { setBusy(false); }
  }
  async function logo(file?: File, remove = false) {
    if (!remove && !file) return;
    if (file && (file.size > MAX_LOGO || !LOGO_TYPES.includes(file.type))) { setError(t('logoInvalid')); return; }
    setBusy(true); setError('');
    try {
      const body = new FormData(); if (file) body.append('file', file);
      load(await apiClient<Record<string, unknown>>('/organization/branding/logo?secondary=true', remove ? { method: 'DELETE' } : { method: 'POST', body }));
    } catch { setError(t('logoError')); } finally { setBusy(false); }
  }

  // The header carries the legal identity on both sides, each in its own language (as printed).
  const legal = ([['cr', data.commercial_registration_no], ['unified', data.unified_number], ['vat', data.vat_number]] as const).filter(([, v]) => v);
  const tAr = (k: string) => ({ cr: 'السجل التجاري', unified: 'الرقم الموحد', vat: 'الرقم الضريبي' } as Record<string, string>)[k];
  const tEn = (k: string) => ({ cr: 'CR No.', unified: 'Unified No.', vat: 'VAT No.' } as Record<string, string>)[k];
  return <section className={s.panel}><h2>{t('title')}</h2>
    <form onSubmit={e => { e.preventDefault(); void save(); }}><div className={s.grid}>{FIELDS.map(key => <label key={key} className={s.field}>{t(`fields.${key}`)}
      <input disabled={!canWrite || busy} type={key === 'primary_color' ? 'color' : key === 'email' ? 'email' : 'text'} dir={key.endsWith('_en') ? 'ltr' : key.endsWith('_ar') ? 'rtl' : undefined}
        value={data[key] ?? (key === 'primary_color' ? DEFAULT_ACCENT : '')} maxLength={key.includes('footer') ? 1000 : key.includes('address') ? 500 : 255}
        pattern={PATTERNS[key]} inputMode={PATTERNS[key] ? 'numeric' : undefined} title={PATTERNS[key] ? t(`formats.${key}`) : undefined}
        onChange={e => { setSaved(false); setData(old => ({ ...old, [key]: e.target.value })); }} /></label>)}</div>
      <h3>{t('banks.title')}</h3>
      <p>{t('banks.hint')}</p>
      {banks.map((bank, index) => <fieldset key={index} className={s.panel} style={{ opacity: bank.is_active ? 1 : 0.6 }}>
        <legend>{t('banks.account', { number: index + 1 })}</legend>
        <div className={s.grid}>{BANK_FIELDS.map(key => <label key={key} className={s.field}>{t(`banks.fields.${key}`)}{key === 'bank_name_ar' || key === 'iban' ? ' *' : ''}
          <input disabled={!canWrite || busy} dir={key === 'bank_name_ar' ? 'rtl' : 'ltr'} value={bank[key] ?? ''} maxLength={key === 'iban' ? 42 : key === 'swift_code' ? 11 : 255}
            required={key === 'bank_name_ar' || key === 'iban'}
            onChange={e => { setSaved(false); setBanks(old => old.map((b, i) => (i === index ? { ...b, [key]: e.target.value } : b))); }} /></label>)}</div>
        {canWrite && <div className={s.actions}>
          <label><input type="checkbox" checked={bank.is_active} disabled={busy}
            onChange={e => setBanks(old => old.map((b, i) => (i === index ? { ...b, is_active: e.target.checked } : b)))} /> {t('banks.active')}</label>
          <button type="button" className={s.button} disabled={busy} onClick={() => setBanks(old => old.filter((_, i) => i !== index))}>{t('banks.remove')}</button>
        </div>}
      </fieldset>)}
      {canWrite && <p><button type="button" className={s.button} disabled={busy || banks.length >= 10} onClick={() => setBanks(old => [...old, emptyBank()])}>{t('banks.add')}</button></p>}
      {canWrite && <div className={s.actions}>
        <button className={`${s.button} ${s.primary}`} disabled={busy}>{t('save')}</button>
        <label className={s.button}>{t('uploadSecondary')}<input hidden type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={e => void logo(e.target.files?.[0])} /></label>
        {data.secondary_logo_data_uri && <button className={s.button} type="button" disabled={busy} onClick={() => void logo(undefined, true)}>{t('removeSecondary')}</button>}
      </div>}
    </form>
    {error && <p role="alert" className={s.error}>{error}</p>}{saved && <p role="status">{t('saved')}</p>}
    <h3>{t('previewTitle')}</h3>
    <p>{t('previewHint')}</p>
    {/* Mirrors the printed header and external footer (backend templates/identity): Arabic right, logo centre, English left. */}
    <div className={s.brandPreview}>
      <header dir="rtl" className={s.brandHeader} style={{ borderColor: data.primary_color ?? DEFAULT_ACCENT }}>
        <div className={s.brandSide} lang="ar">
          <strong style={{ color: data.primary_color ?? DEFAULT_ACCENT }}>{data.legal_name_ar || data.name}</strong>
          {data.descriptor_ar && <small>{data.descriptor_ar}</small>}
          <dl className={s.brandLegal}>{legal.map(([k, v]) => <div key={k}><dt>{tAr(k)}</dt><dd dir="ltr">{v}</dd></div>)}</dl>
        </div>
        <div className={s.brandLogo}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {data.logo_data_uri && <img src={data.logo_data_uri} alt={t('logoAlt')} />}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {data.secondary_logo_data_uri && <img src={data.secondary_logo_data_uri} alt={t('secondaryLogoAlt')} />}
        </div>
        <div className={s.brandSide} lang="en" dir="ltr">
          <strong style={{ color: data.primary_color ?? DEFAULT_ACCENT }}>{data.legal_name_en}</strong>
          {data.descriptor_en && <small>{data.descriptor_en}</small>}
          <dl className={s.brandLegal}>{legal.map(([k, v]) => <div key={k}><dt>{tEn(k)}</dt><dd>{v}</dd></div>)}</dl>
        </div>
      </header>
      <footer className={s.brandFooter} dir={ar ? 'rtl' : 'ltr'} style={{ borderColor: data.primary_color ?? DEFAULT_ACCENT }}>
        <div className={s.brandColumns}>
          <dl>{([['address', data[ar ? 'address_ar' : 'address_en']], ['phone', data.phone], ['email', data.email], ['website', data.website]] as const)
            .filter(([, v]) => v).map(([k, v]) => <div key={k}><dt>{t(`labels.${k}`)}</dt><dd>{v}</dd></div>)}</dl>
          {banks.some(b => b.is_active && b.iban) && <dl>{banks.filter(b => b.is_active && b.iban).map((b, i) =>
            <div key={i} className={s.brandBank}><b>{ar ? b.bank_name_ar : b.bank_name_en || b.bank_name_ar}</b><span dir="ltr">IBAN {b.iban}</span></div>)}</dl>}
        </div>
        <div className={s.brandStrip}><b>{data[ar ? 'legal_name_ar' : 'legal_name_en'] || data.legal_name_ar || data.name}</b><span>{t('previewPage')}</span></div>
      </footer>
    </div>
  </section>;
}
