"use client";
import {useUnitLabel} from "@/components/UnitLabel";
import { useEffect, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { sharedStyles } from '@/styles/shared-styles';
import { getSampleProducts } from '../api/samples-api';
import type { RequestedSpec, SampleProductDefinition } from '../types';

/** Render historical nested values without exposing raw JSON or enabling edits to unknown fields. */
function ReadableValue({ value }: { value: unknown }) {
  const unitText = useUnitLabel();
  const t = useTranslations('commercial.samples.properties');
  if (value === null || value === undefined || value === '') return <>—</>;
  if (typeof value === 'boolean') return <>{t(value ? 'yes' : 'no')}</>;
  if (Array.isArray(value)) return <ul>{value.map((v, i) => <li key={i}><ReadableValue value={v} /></li>)}</ul>;
  if (typeof value === 'object') return <dl>{Object.entries(value).map(([k, v]) => <div key={k}><dt>{k}</dt><dd><ReadableValue value={v} /></dd></div>)}</dl>;
  return <bdi>{String(value)}</bdi>;
}

export function SamplePropertyValues({ values, definition }: { values: RequestedSpec | null; definition?: SampleProductDefinition | null }) {
  const ar = useLocale() === 'ar';
  const unitText = useUnitLabel();
  const t = useTranslations('commercial.samples.properties');
  const props = definition?.properties ?? [];
  const keys = [...props.map(p => p.key).filter(k => values && k in values), ...Object.keys(values ?? {}).filter(k => !props.some(p => p.key === k))];
  if (!keys.length) return <p>{t('empty')}</p>;
  return <dl style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
    {keys.map(key => {
      const prop = props.find(p => p.key === key);
      const choice = prop?.options?.find(o => o.value === values?.[key]);
      const label = prop ? (ar ? prop.name_ar : prop.name_en) : key;
      return <div key={key}><dt style={{ fontWeight: 600 }}>{label}{prop?.unit ? ` (${unitText(prop.unit)})` : ''}</dt>
        <dd style={{ margin: 0, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}><ReadableValue value={choice ? (ar ? choice.label_ar : choice.label_en) : values?.[key]} /></dd></div>;
    })}
  </dl>;
}

/** Only schema-defined fields can be edited. Master Data owns names, kinds, required flags and options. */
export function SampleProductFields({ productKey, values, original, unchanged = false, disabled, onChange, onReady }: {
  productKey: string; values: RequestedSpec; original?: SampleProductDefinition | null; unchanged?: boolean; disabled: boolean;
  onChange: (key: string, values: RequestedSpec, unit?: string | null) => void; onReady: (ready: boolean) => void;
}) {
  const ar = useLocale() === 'ar';
  const unitText = useUnitLabel();
  const t = useTranslations('commercial.samples.properties');
  const [products, setProducts] = useState<SampleProductDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true; setLoading(true); setFailed(false);
    getSampleProducts().then(rows => { if (active) setProducts(rows); }).catch(() => { if (active) setFailed(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [retry]);
  const product = products.find(p => p.key === productKey) ?? (original?.key === productKey ? original : undefined);
  useEffect(() => { onReady(unchanged || (!loading && !failed && Boolean(product))); }, [unchanged, loading, failed, product, onReady]);
  function changeProperty(key: string, value: unknown) {
    const next = { ...values, [key]: value };
    for (const prop of product?.properties ?? []) {
      const v = next[prop.key];
      if (v === '') delete next[prop.key];
      else if (prop.kind === 'number' && typeof v === 'string' && v.trim() && Number.isFinite(Number(v))) next[prop.key] = Number(v);
    }
    onChange(productKey, next);
  }
  const extra = Object.fromEntries(Object.entries(values).filter(([key]) => !product?.properties.some(p => p.key === key)));
  return <section style={{ display: 'grid', gap: 16 }}>
    <label style={sharedStyles.field}><span style={sharedStyles.label}>{t('product')} *</span>
      <select style={sharedStyles.input} aria-label={t('product')} value={productKey} required disabled={disabled || loading || failed}
        onChange={e => { const p = products.find(p => p.key === e.target.value); onChange(e.target.value, {}, p?.default_unit); }}>
        <option value="">{loading ? t('loading') : t('choose')}</option>
        {products.map(p => <option key={p.key} value={p.key}>{ar ? p.name_ar : p.name_en}</option>)}
        {productKey && !products.some(p => p.key === productKey) && <option value={productKey}>{product ? (ar ? product.name_ar : product.name_en) : productKey} — {t('legacy')}</option>}
      </select>
    </label>
    {failed && <div role="alert">{t('loadError')} <button type="button" onClick={() => setRetry(n => n + 1)}>{t('retry')}</button></div>}
    {!loading && !failed && !products.length && <p>{t('noProducts')}</p>}
    {product && <fieldset disabled={disabled || loading || failed} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
      <legend>{t('title')}</legend>
      {!product.properties.length && <p>{t('noProperties')}</p>}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
        {product.properties.map(p => {
          const label = ar ? p.name_ar : p.name_en;
          const raw = values[p.key];
          const value = typeof raw === 'string' || typeof raw === 'number' ? String(raw) : '';
          return <label key={p.key} style={sharedStyles.field}><span>{label}{p.unit ? ` (${unitText(p.unit)})` : ''}{p.required ? ' *' : ''}</span>
            {p.kind === 'choice' ? <select aria-label={label} style={sharedStyles.input} value={value} required={p.required && !unchanged}
              onChange={e => changeProperty(p.key, e.target.value)}>
              <option value="">—</option>{p.options?.map(o => <option key={o.value} value={o.value}>{ar ? o.label_ar : o.label_en}</option>)}
              {value && !p.options?.some(o => o.value === value) && <option value={value} disabled>{value} — {t('legacy')}</option>}
            </select> : <input aria-label={label} style={sharedStyles.input} type={p.kind === 'number' ? 'number' : 'text'} step={p.kind === 'number' ? 'any' : undefined}
              value={value} required={p.required && !unchanged} onChange={e => changeProperty(p.key, e.target.value)} />}
          </label>;
        })}
      </div>
    </fieldset>}
    {Object.keys(extra).length > 0 && <section><h3>{t('legacyValues')}</h3><p>{t('preserved')}</p><SamplePropertyValues values={extra} /></section>}
    {unchanged && <small>{t('unchanged')}</small>}
  </section>;
}
