"use client";
import { useEffect, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Definition, Schema, getDefinitions, getLookups, reportRequest } from './api';
import s from './reports.module.css';

export function resolveSchema(field: Schema, root: Schema): Schema {
  if (field.$ref) return { ...root.$defs?.[field.$ref.split('/').pop()!], ...field };
  if (field.anyOf) return { ...resolveSchema(field.anyOf.find(x => x.type !== 'null') ?? {}, root), ...field };
  return field;
}

function Lookup({ kind, value, onChange, required, label, module }: { module: string; kind: string; value: string; onChange: (v: string) => void; required: boolean; label: string }) {
  const t = useTranslations('reports.form');
  const [query, setQuery] = useState(''); const [options, setOptions] = useState<{ id: string; label: string }[]>([]);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => { getLookups(kind, query, module).then(v => { if (active) setOptions(v); }).catch(() => { if (active) setOptions([]); }); }, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [kind, query, module]);
  return <>
    <input aria-label={t('searchFor', { field: label })} value={query} onChange={e => setQuery(e.target.value)} placeholder={t('search')} />
    <select aria-label={label} required={required} value={value} onChange={e => onChange(e.target.value)}>
      <option value="">—</option>
      {value && !options.some(o => o.id === value) && <option value={value}>{value}</option>}
      {options.map(o => <option value={o.id} key={o.id}>{o.label}</option>)}
    </select>
  </>;
}

// Fields come from the report's definition (its JSON schema); labels and messages from the locale files.
export function ReportForm({ definition, fixedParams = {} }: { definition: Definition; fixedParams?: Record<string, string> }) {
  const t = useTranslations('reports');
  const locale = useLocale(), ar = locale === 'ar';
  const initial = Object.fromEntries(Object.entries(definition.params_schema.properties ?? {}).filter(([, v]) => v.default !== undefined && v.default !== null).map(([k, v]) => [k, v.default]));
  const [values, setValues] = useState<Record<string, unknown>>({ ...initial, ...fixedParams, ...(definition.audiences?.length ? { audience: definition.audiences.includes(String(initial.audience)) ? initial.audience : definition.audiences[0] } : {}), lang: locale, orientation: definition.default_orientation });
  const [sections, setSections] = useState(definition.sections.filter(x => x.default_enabled).map(x => x.key));
  const [available, setAvailable] = useState(definition.sections);
  const [html, setHtml] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const param = (k: string) => (t.has(`params.${k}`) ? t(`params.${k}`) : k);
  const option = (v: string) => (t.has(`values.${v}`) ? t(`values.${v}`) : v);

  const reportModule = definition.module ?? definition.key.split('.')[0];
  const context = Object.fromEntries((definition.context_fields ?? []).filter(k => values[k]).map(k => [k, String(values[k])]));
  if (values.audience) context.audience = String(values.audience);
  const contextKey = JSON.stringify(context);
  useEffect(() => {
    if (!definition.context_fields?.length && !definition.audiences?.length) return;
    let active = true;
    getDefinitions(reportModule, JSON.parse(contextKey)).then(ds => {
      if (!active) return;
      const next = ds.find(d => d.key === definition.key)?.sections ?? [];
      setAvailable(next); setSections(next.filter(x => x.default_enabled).map(x => x.key));
    }).catch(() => { if (active) { setAvailable([]); setSections([]); } });
    return () => { active = false; };
  }, [definition.key, definition.context_fields, definition.audiences, reportModule, contextKey]);

  async function run(format: 'preview' | 'pdf') {
    setBusy(true); setError('');
    try {
      const params: Record<string, unknown> = { ...values, sections };
      Object.keys(params).forEach(k => { if (params[k] === '') delete params[k]; });
      const result = await reportRequest(definition.key, format, params);
      if (result.html) setHtml(result.html);
    } catch (e) {
      const code = e instanceof Error ? e.message : '';
      setError(t.has(`errors.${code}`) ? t(`errors.${code}`) : t('errors.default'));
    } finally { setBusy(false); }
  }

  return <section className={s.panel}><form onSubmit={e => { e.preventDefault(); void run('preview'); }}>
    <div className={s.grid}>{Object.entries(definition.params_schema.properties ?? {}).filter(([key]) => !['sections', 'lang', 'orientation', 'audience'].includes(key) && !(key in fixedParams)).map(([key, raw]) => {
      const field = resolveSchema(raw, definition.params_schema), required = definition.params_schema.required?.includes(key) ?? false;
      const title = (ar ? raw.title_ar : raw.title_en) ?? param(key), value = values[key] ?? ''; const set = (v: unknown) => setValues(old => ({ ...old, [key]: v }));
      const options = field.type === 'array' ? resolveSchema(field.items ?? {}, definition.params_schema).enum : field.enum;
      return <label className={s.field} key={key}><span>{title}{required ? ' *' : ''}</span>
        {field.lookup ? <Lookup module={reportModule} kind={field.lookup} value={String(value)} onChange={set} required={required} label={title} />
          : options ? <select aria-label={title} multiple={field.type === 'array'} value={field.type === 'array' ? (Array.isArray(value) ? value : []) : String(value)}
            onChange={e => set(field.type === 'array' ? Array.from(e.target.selectedOptions, o => o.value) : e.target.value)}>
            {!required && field.type !== 'array' && field.default === undefined && <option value="">—</option>}
            {options.map(o => <option key={o} value={o}>{option(o)}</option>)}
          </select>
            : field.type === 'boolean' ? <input type="checkbox" checked={Boolean(value)} onChange={e => set(e.target.checked)} />
              : <input required={required} type={field.format === 'date' ? 'date' : field.type === 'integer' ? 'number' : 'text'} value={String(value)} onChange={e => set(e.target.value)} />}
      </label>;
    })}
      {(definition.audiences?.length ?? 0) > 1 && <label className={s.field}>{t('form.audience')}<select aria-label={t('form.audience')} value={String(values.audience)} onChange={e => setValues(v => ({ ...v, audience: e.target.value }))}>{definition.audiences?.map(a => <option key={a} value={a}>{t('values.'+a)}</option>)}</select></label>}
      <label className={s.field}>{t('form.language')}<select value={String(values.lang)} onChange={e => setValues(v => ({ ...v, lang: e.target.value }))}>
        <option value="ar">{t('form.arabic')}</option><option value="en">{t('form.english')}</option></select></label>
      <label className={s.field}>{t('form.orientation')}<select value={String(values.orientation)} onChange={e => setValues(v => ({ ...v, orientation: e.target.value }))}>
        <option value="portrait">{t('form.portrait')}</option><option value="landscape">{t('form.landscape')}</option></select></label>
    </div>
    <fieldset className={s.toggles}><legend>{t('form.sections')}</legend>{available.map(section => <label key={section.key}>
      <input type="checkbox" checked={sections.includes(section.key)} onChange={e => setSections(old => e.target.checked ? [...old, section.key] : old.filter(k => k !== section.key))} />
      {ar ? section.title_ar : section.title_en}</label>)}</fieldset>
    {error && <p role="alert" className={s.error}>{error}</p>}
    <div className={s.actions}>
      <button className={`${s.button} ${s.primary}`} disabled={busy}>{busy ? t('form.preparing') : t('form.preview')}</button>
      <button type="button" className={s.button} disabled={busy} onClick={e => { if (e.currentTarget.form?.reportValidity()) void run('pdf'); }}>{t('form.download')}</button>
    </div>
  </form>{html && <iframe title={t('form.previewTitle')} sandbox="" srcDoc={html} className={s.preview} />}</section>;
}
