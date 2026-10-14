"use client";
import Link from 'next/link';
import { useEffect, useState, useCallback, type FormEvent, type ReactNode } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { PageFrame } from '@/components/layout/page-frame';
import { PermissionGuard } from '@/components/PermissionGuard';
import { Pagination } from '@/components/pagination/Pagination';
import { UnitSelect } from '@/components/forms/UnitSelect';
import { usePermission } from '@/features/auth/permission-hooks';
import { RecordReportButton } from '@/features/reports/RecordReportButton';
import { useFormatter } from '@/hooks/useFormatter';
import { useListQuery, type Page } from '@/lib/pagination';
import { apiClient } from '@/lib/api-client';
import { root, listComplaints, getComplaint, createComplaint, changeComplaint, saveItems, listProducts, listSources,
  type Complaint, type Item, type ItemDraft, type Product, type Source } from './api';
import { describeEvent } from './history';
import s from './complaints.module.css';
import { FilePicker } from '@/components/forms/FilePicker';
import { Signatures } from "@/components/Signatures";
import { useListChoices, useListName } from '@/features/masterdata';

const prefix = 'commercial:complaints:';
const STATUSES = ['new', 'processing', 'pending_closure', 'closed', 'cancelled'];
const DEPARTMENTS = ['commercial', 'quality', 'shipping', 'production'];
const CATEGORIES = ['quality', 'delivery', 'quantity', 'packaging', 'commercial', 'service', 'other'];  // the usual ones (MD-003)
const PRIORITIES = ['low', 'medium', 'high', 'critical'];
const CHANNELS = ['email', 'phone', 'visit', 'message', 'other'];
const FINDINGS = ['pending', 'verified', 'not_verified', 'inconclusive'];
const KINDS = ['order', 'shipment', 'return', 'ncr'];
const SUMMARY = ['active', 'overdue', 'response_overdue', 'pending_closure', 'closed'];
const FORMS = ['assign', 'investigate', 'resolve', 'items', 'communicate', 'refer_quality', 'link', 'attach'];

/** The one decision the complaint waits for now (ISO 10002 order), when the user may take it. */
function nextStep(row: Complaint | null): string | null {
  if (!row) return null;
  const may = (a: string) => (row.actions.includes(a) ? a : null);
  if (row.status === 'new') return may('assign');
  if (row.status === 'pending_closure') return may('approve_close');
  if (row.status !== 'processing') return null;
  if (row.finding === 'pending' || !row.investigation) return may('investigate');
  if (!row.resolution || !row.implementation_evidence || !row.customer_response) return may('resolve');
  return may('request_close');
}

function useWords() {
  const t = useTranslations('commercial.complaints');
  const units = useTranslations('common.units.units');
  const ar = useLocale() === 'ar';
  const unit = useCallback((code: string | null | undefined) => (code && units.has(code) ? units(code) : code ?? ''), [units]);
  // The product's name in the reader's language when the catalogue has it, else the name the line stored.
  const named = useCallback((products: Product[], key: string, stored?: string) => {
    const p = products.find(x => x.key === key);
    return p ? (ar ? p.name_ar : p.name_en) : stored || key;
  }, [ar]);
  return { t, ar, unit, named };
}

function errorText(e: unknown, t: ReturnType<typeof useTranslations>, fallback: string) {
  const d = (e as { details?: { detail?: unknown } })?.details?.detail;
  return typeof d === 'string' && t.has(`errors.${d}`) ? t(`errors.${d}`) : fallback;
}

function Field({ name, children }: { name: string; children: ReactNode }) {
  return <label className={s.field}>{name}{children}</label>;
}

function Frame({ children }: { children: ReactNode }) {
  const { t } = useWords();
  return <PageFrame title={t('title')}><PermissionGuard code={prefix + 'read'}>{children}</PermissionGuard></PageFrame>;
}

export function ComplaintsList() {
  const { t } = useWords(), fmt = useFormatter();
  const list = useListQuery(['search', 'status', 'department', 'customer_id', 'overdue'] as const), query = list.apiQuery();
  const [data, setData] = useState<Page<Complaint> | null>(null), [error, setError] = useState(''), [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<Record<string, number> | null>(null);
  const canCreate = usePermission(prefix + 'create');
  useEffect(() => {
    let live = true;
    const q = new URLSearchParams();
    if (list.filters.customer_id) q.set('customer_id', list.filters.customer_id);
    if (list.filters.department) q.set('department', list.filters.department);
    apiClient<Record<string, number>>(root + '/summary?' + q).then(v => { if (live) setSummary(v); }).catch(() => { if (live) setSummary(null); });
    return () => { live = false; };
  }, [list.filters.customer_id, list.filters.department]);
  useEffect(() => {
    let live = true;
    setLoading(true); setError('');
    listComplaints(query).then(d => { if (live) setData(d); }).catch(() => { if (live) setError(t('loadFailed')); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [query, t]);
  return <Frame>
    <div className={s.header}>
      <div><h1>{t('title')}</h1><p className={s.muted}>{t('subtitle')}</p></div>
      {canCreate && <Link className={`${s.button} ${s.primary}`} href={`/complaints/new${list.filters.customer_id ? '?customer_id=' + list.filters.customer_id : ''}`}>{t('register')}</Link>}
    </div>
    {summary && <div className={s.grid}>{SUMMARY.map(k => <div className={s.panel} key={k}><span className={s.muted}>{t(`summary.${k}`)}</span><div className={s.metric}>{summary[k]}</div></div>)}</div>}
    <div className={s.toolbar}>
      <input aria-label={t('search')} placeholder={t('searchPlaceholder')} value={list.filters.search} onChange={e => list.setFilter('search', e.target.value)} />
      <select aria-label={t('fields.status')} value={list.filters.status} onChange={e => list.setFilter('status', e.target.value)}>
        <option value="">{t('allStatuses')}</option>{STATUSES.map(k => <option key={k} value={k}>{t(`statuses.${k}`)}</option>)}
      </select>
      <select aria-label={t('fields.department')} value={list.filters.department} onChange={e => list.setFilter('department', e.target.value)}>
        <option value="">{t('allDepartments')}</option>{DEPARTMENTS.map(k => <option key={k} value={k}>{t(`departments.${k}`)}</option>)}
      </select>
      <label><input type="checkbox" checked={list.filters.overdue === 'true'} onChange={e => list.setFilter('overdue', e.target.checked ? 'true' : '')} style={{ width: 'auto' }} /> {t('overdueOnly')}</label>
    </div>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {loading ? <p role="status">{t('loading')}</p> : <section className={s.panel}>
      {!data?.items.length ? <p>{t('empty')}</p> : <div className={s.tableWrap}><table className={s.table}>
        <thead><tr>{(['number', 'customerSubject', 'status', 'priority', 'owner', 'due'] as const).map(k => <th key={k}>{t(`columns.${k}`)}</th>)}</tr></thead>
        <tbody>{data.items.map(r => <tr key={r.id}>
          <td><Link href={'/complaints/' + r.id}>{r.number}</Link></td>
          <td>{r.customer_name}<br />{r.title}</td>
          <td><span className={s.badge}>{t(`statuses.${r.status}`)}</span></td>
          <td>{t(`priorities.${r.priority}`)}</td>
          <td>{r.owner_name || t('unassigned')}<br />{t(`departments.${r.department}`)}</td>
          <td className={r.overdue ? s.error : ''}>{fmt.date(r.due_date)}{r.overdue && <div>{t('overdue')}</div>}</td>
        </tr>)}</tbody>
      </table></div>}
      {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} pages={data.pages} onPage={list.setPage} onPageSize={list.setPageSize} />}
    </section>}
  </Frame>;
}

type Option = { id: string; name?: string; label?: string };
function SearchSelect({ endpoint, value, onChange, title }: { endpoint: string; value: string; onChange: (s: string) => void; title: string }) {
  const { t } = useWords();
  const [search, setSearch] = useState(''), [options, setOptions] = useState<Option[]>([]), [chosen, setChosen] = useState<Option | null>(null), [error, setError] = useState(false);
  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => {
      apiClient<Option[]>(endpoint + (endpoint.includes('?') ? '&' : '?') + 'search=' + encodeURIComponent(search))
        .then(v => { if (live) { setOptions(v); setError(false); } }).catch(() => { if (live) setError(true); });
    }, 250);
    return () => { live = false; clearTimeout(timer); };
  }, [endpoint, search]);
  useEffect(() => {
    if (!value || !endpoint.endsWith('/customers')) return;
    let live = true;
    apiClient<Option[]>(endpoint + '?id=' + encodeURIComponent(value)).then(v => { if (live) setChosen(v[0] || null); }).catch(() => {});
    return () => { live = false; };
  }, [endpoint, value]);
  const shown = chosen && !options.some(o => o.id === chosen.id) ? [chosen, ...options] : options;
  return <Field name={title}>
    <input aria-label={t('picker.search', { title })} placeholder={t('picker.placeholder')} value={search} onChange={e => setSearch(e.target.value)} />
    <select required value={value} onChange={e => { onChange(e.target.value); setChosen(options.find(o => o.id === e.target.value) || null); }}>
      <option value="">{t('picker.choose')}</option>{shown.map(o => <option key={o.id} value={o.id}>{o.name || o.label}</option>)}
    </select>
    {error && <small role="alert">{t('picker.unavailable')}</small>}
  </Field>;
}

const emptyLine = (): ItemDraft => ({ product_key: '', source_kind: 'manual', source_id: null, batch_reference: '', unit: '', delivered_quantity: '', reported_quantity: '', properties: [] });

// Only the properties the line says something about (an agreed value from a source is added by the server).
const cleaned = (items: ItemDraft[]) => items.map(i => ({ ...i, properties: i.properties.filter(p => p.expected || p.reported) }));

export const draftOf = (item: Item): ItemDraft => ({ id: item.id, product_key: item.product_key, source_kind: item.source_kind, source_id: item.source_id,
  batch_reference: item.batch_reference ?? '', unit: item.unit, delivered_quantity: String(item.delivered_quantity), reported_quantity: String(item.reported_quantity),
  properties: item.properties.map(p => ({ key: p.key, expected: p.expected, reported: p.reported })) });

/**
 * The complaint's product lines. The agreed values come from a sales order line or a sample of the customer when one is
 * chosen (the server copies them), otherwise they are typed; the customer's reported value is typed in every case.
 */
function ItemsEditor({ customerId, products, items, onChange }: { customerId: string; products: Product[]; items: ItemDraft[]; onChange: (items: ItemDraft[]) => void }) {
  const { t, ar, unit, named } = useWords();
  const [sources, setSources] = useState<Source[]>([]);
  useEffect(() => {
    if (!customerId) { setSources([]); return; }
    let live = true;
    listSources(customerId).then(v => { if (live) setSources(v); }).catch(() => { if (live) setSources([]); });
    return () => { live = false; };
  }, [customerId]);
  const patch = (i: number, change: Partial<ItemDraft>) => onChange(items.map((r, n) => (n === i ? { ...r, ...change } : r)));
  const choose = (i: number, key: string) => {
    const p = products.find(x => x.key === key);
    patch(i, { product_key: key, source_kind: 'manual', source_id: null, unit: p?.default_unit || '', properties: p?.properties.map(x => ({ key: x.key, expected: '', reported: '' })) || [] });
  };
  const pickSource = (i: number, value: string) => {
    const found = sources.find(x => `${x.kind}:${x.id}` === value);
    if (!found) { patch(i, { source_kind: 'manual', source_id: null }); return; }
    const item = items[i];
    patch(i, { source_kind: found.kind, source_id: found.id, unit: item.unit || found.unit || '',
      properties: item.properties.map(p => ({ ...p, expected: found.spec[p.key] ?? '' })) });
  };
  return <>
    {items.map((item, i) => {
      const product = products.find(p => p.key === item.product_key);
      const matching = sources.filter(x => x.product_key === item.product_key);
      const source = sources.find(x => x.kind === item.source_kind && x.id === item.source_id);
      return <section className={s.panel} key={item.id ?? `new-${i}`}>
        <div className={s.grid}>
          <Field name={t('items.product')}>
            <select required value={item.product_key} onChange={e => choose(i, e.target.value)}>
              <option value="">{t('items.chooseProduct')}</option>
              {products.map(p => <option key={p.key} value={p.key}>{ar ? p.name_ar : p.name_en}</option>)}
            </select>
          </Field>
          {item.product_key && <Field name={t('items.source')}>
            <select value={item.source_id ? `${item.source_kind}:${item.source_id}` : ''} onChange={e => pickSource(i, e.target.value)}>
              <option value="">{t('items.manual')}</option>
              {matching.map(x => <option key={x.kind + x.id} value={`${x.kind}:${x.id}`}>{`${t(`kinds.${x.kind}`)} ${x.label}`}</option>)}
            </select>
          </Field>}
          <Field name={t('items.unit')}><UnitSelect value={item.unit} onChange={v => patch(i, { unit: v })} required /></Field>
          <Field name={t('items.delivered')}><input required type="number" min="0" step="0.001" value={item.delivered_quantity} onChange={e => patch(i, { delivered_quantity: e.target.value })} /></Field>
          <Field name={t('items.reported')}><input required type="number" min="0" max={item.delivered_quantity || undefined} step="0.001" value={item.reported_quantity} onChange={e => patch(i, { reported_quantity: e.target.value })} /></Field>
          <Field name={t('items.batch')}><input maxLength={255} value={item.batch_reference} onChange={e => patch(i, { batch_reference: e.target.value })} /></Field>
        </div>
        {source && <p className={s.muted}>{t('items.fromSource', { source: `${t(`kinds.${source.kind}`)} ${source.label}` })}</p>}
        {product && <div className={s.tableWrap}><table className={s.table}>
          <thead><tr><th>{t('items.property')}</th><th>{t('items.expected')}</th><th>{t('items.reportedValue')}</th></tr></thead>
          <tbody>{item.properties.map((p, j) => {
            const def = product.properties.find(x => x.key === p.key);
            const name = def ? (ar ? def.name_ar : def.name_en) : p.key;
            const set = (k: 'expected' | 'reported', v: string) => patch(i, { properties: item.properties.map((x, n) => (n === j ? { ...x, [k]: v } : x)) });
            return <tr key={p.key}>
              <td>{name}{def?.unit ? ` (${unit(def.unit)})` : ''}</td>
              <td>{item.source_id ? (p.expected || '—')
                : <input aria-label={`${name} — ${t('items.expected')}`} maxLength={1000} value={p.expected} onChange={e => set('expected', e.target.value)} />}</td>
              <td><input aria-label={`${name} — ${t('items.reportedValue')}`} maxLength={1000} value={p.reported} onChange={e => set('reported', e.target.value)} /></td>
            </tr>;
          })}</tbody>
        </table></div>}
        {item.product_key && !product && <p className={s.muted}>{named(products, item.product_key)}</p>}
        <button type="button" className={s.button} onClick={() => onChange(items.filter((_, n) => n !== i))}>{t('items.remove')}</button>
      </section>;
    })}
    <button type="button" className={s.button} onClick={() => onChange([...items, emptyLine()])}>{t('items.add')}</button>
  </>;
}

export function ComplaintCreate({ customerId = '' }: { customerId?: string }) {
  const { t } = useWords(), router = useRouter();
  const [values, setValues] = useState({ customer_id: customerId, title: '', statement: '', contact: '', channel: 'email', received_date: new Date().toLocaleDateString('en-CA'),
    category: 'quality', priority: 'medium', due_date: '', response_due_date: '', external_reference: '' });
  const [products, setProducts] = useState<Product[]>([]), [items, setItems] = useState<ItemDraft[]>([]), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const set = (key: string, value: string) => setValues(v => ({ ...v, [key]: value }));
  const categoryChoices = useListChoices('complaint_category', CATEGORIES, k => (t.has(`categories.${k}`) ? t(`categories.${k}`) : k), values.category);
  useEffect(() => { listProducts().then(setProducts).catch(() => setError(t('errors.products'))); }, [t]);
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('');
    try {
      const r = await createComplaint({ ...values, due_date: values.due_date || null, response_due_date: values.response_due_date || null, items: cleaned(items) });
      router.push('/complaints/' + r.id);
    } catch (err) { setError(errorText(err, t, t('errors.save'))); } finally { setBusy(false); }
  }
  const select = (key: keyof typeof values, group: string, keys: string[]) =>
    <select value={values[key]} onChange={e => set(key, e.target.value)}>{keys.map(k => <option key={k} value={k}>{t(`${group}.${k}`)}</option>)}</select>;
  return <Frame><PermissionGuard code={prefix + 'create'}>
    <Link href="/complaints">← {t('back')}</Link>
    <h1>{t('registerTitle')}</h1><p className={s.muted}>{t('registerHint')}</p>
    <form onSubmit={submit}><fieldset disabled={busy} style={{ border: 0, padding: 0 }}>
      <section className={s.panel}><div className={s.grid}>
        <SearchSelect endpoint={root + '/customers'} value={values.customer_id} onChange={v => { set('customer_id', v); setItems(rows => rows.map(r => ({ ...r, source_kind: 'manual', source_id: null }))); }} title={t('fields.customer')} />
        <Field name={t('fields.subject')}><input required maxLength={255} value={values.title} onChange={e => set('title', e.target.value)} /></Field>
        <Field name={t('fields.receivedDate')}><input required type="date" value={values.received_date} onChange={e => set('received_date', e.target.value)} /></Field>
        <Field name={t('fields.category')}><select value={values.category} onChange={e => set('category', e.target.value)}>
          {categoryChoices.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}</select></Field>
        <Field name={t('fields.priority')}>{select('priority', 'priorities', PRIORITIES)}</Field>
        <Field name={t('fields.channel')}>{select('channel', 'channels', CHANNELS)}</Field>
        <Field name={t('fields.resolutionDue')}><input type="date" min={values.received_date} value={values.due_date} onChange={e => set('due_date', e.target.value)} /></Field>
      </div>
      <div style={{ marginTop: 16 }}><Field name={t('fields.statement')}><textarea required maxLength={10000} value={values.statement} onChange={e => set('statement', e.target.value)} /></Field></div>
      <details className={s.more}><summary>{t('moreDetails')}</summary><div className={s.grid}>
        <Field name={t('fields.contact')}><input maxLength={255} value={values.contact} onChange={e => set('contact', e.target.value)} /></Field>
        <Field name={t('fields.responseDue')}><input type="date" min={values.received_date} value={values.response_due_date} onChange={e => set('response_due_date', e.target.value)} /></Field>
        <Field name={t('fields.externalReference')}><input maxLength={255} value={values.external_reference} onChange={e => set('external_reference', e.target.value)} /></Field>
      </div></details></section>
      <section className={s.panel}><h2>{t('items.title')}</h2><p className={s.muted}>{t('items.hint')}</p>
        <ItemsEditor customerId={values.customer_id} products={products} items={items} onChange={setItems} /></section>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <button className={`${s.button} ${s.primary}`} disabled={busy}>{busy ? t('form.saving') : t('register')}</button>
    </fieldset></form>
  </PermissionGuard></Frame>;
}

type Findings = Record<string, { confirmed: string; measured: Record<string, string> }>;

export function ComplaintDetail({ id }: { id: string }) {
  const { t, ar, unit, named } = useWords(), fmt = useFormatter();
  const categoryName = useListName('complaint_category', k => (t.has(`categories.${k}`) ? t(`categories.${k}`) : undefined));
  const [row, setRow] = useState<Complaint | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false), [operation, setOperation] = useState('');
  const [fields, setFields] = useState<Record<string, string>>({}), [file, setFile] = useState<File | null>(null);
  const [products, setProducts] = useState<Product[]>([]), [drafts, setDrafts] = useState<ItemDraft[]>([]), [findings, setFindings] = useState<Findings>({});
  const set = (k: string, v: string) => setFields(f => ({ ...f, [k]: v }));
  useEffect(() => {
    let live = true;
    getComplaint(id).then(r => { if (live) setRow(r); }).catch(() => { if (live) setError(t('detailFailed')); });
    listProducts().then(v => { if (live) setProducts(v); }).catch(() => {});
    return () => { live = false; };
  }, [id, t]);
  function open(op: string) {
    if (!row) return;
    setOperation(op); setError(''); setFile(null);
    setFields({ department: row.department || 'commercial', due_date: row.due_date || '', finding: row.finding || 'pending', investigation: row.investigation || '',
      containment: row.containment || '', resolution: row.resolution || '',
      implementation_evidence: row.implementation_evidence || '', customer_response: row.customer_response || '', kind: 'ncr' });
    setDrafts(row.items.map(draftOf));
    setFindings(Object.fromEntries(row.items.map(i => [i.id, { confirmed: i.confirmed_quantity == null ? '' : String(i.confirmed_quantity),
      measured: Object.fromEntries(i.properties.map(p => [p.key, p.measured])) }])));
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!row) return;
    setBusy(true); setError('');
    try {
      let result: Complaint;
      const body: Record<string, unknown> = { version: row.version };
      const keys: Record<string, string[]> = { assign: ['owner_user_id', 'department', 'due_date', 'reason'], investigate: ['finding', 'investigation', 'containment'],
        resolve: ['resolution', 'implementation_evidence', 'customer_response'], communicate: ['notes'], refer_quality: ['notes'], link: ['kind', 'record_id'] };
      const endpoints: Record<string, string> = { refer_quality: 'refer-quality', communicate: 'communications', link: 'links' };
      if (operation === 'attach') {
        if (!file) return;
        const form = new FormData(); form.set('version', String(row.version)); form.set('file', file);
        result = await apiClient<Complaint>(`${root}/${id}/attachments`, { method: 'POST', body: form });
      } else if (operation === 'items') {
        result = await saveItems(id, { version: row.version, items: cleaned(drafts) });
      } else if (keys[operation]) {
        for (const k of keys[operation]) body[k] = fields[k] || '';
        if (operation === 'communicate') body.to_customer = fields.to_customer === 'true';
        if (operation === 'investigate') {
          body.items = row.items.map(i => ({ item_id: i.id, confirmed_quantity: findings[i.id]?.confirmed || null,
            measurements: i.properties.map(p => ({ key: p.key, measured: findings[i.id]?.measured[p.key] ?? '' })) }));
        }
        result = await changeComplaint(id, endpoints[operation] ?? operation, body);
      } else {
        result = await changeComplaint(id, 'transitions', { ...body, action: operation, reason: fields.reason });
      }
      setRow(result); setOperation('');
    } catch (err) { setError(errorText(err, t, t('errors.action'))); } finally { setBusy(false); }
  }
  async function download(a: { id: string; filename: string }) {
    try {
      const response = await apiClient<Response>(`${root}/${id}/attachments/${a.id}`, { raw: true });
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a'); link.href = url; link.download = a.filename; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setError(t('errors.download')); }
  }
  const text = (key: string, title: string, required = true) =>
    <Field name={title}><textarea required={required} maxLength={10000} value={fields[key] || ''} onChange={e => set(key, e.target.value)} /></Field>;
  const measure = (itemId: string, change: Partial<Findings[string]>) => setFindings(f => ({ ...f, [itemId]: { ...f[itemId], ...change } }));
  const quantity = (v: string | null, u: string) => (v == null || v === '' ? '—' : `${fmt.decimal(v)} ${unit(u)}`);
  const next = nextStep(row);
  const others = row ? row.actions.filter(a => a !== next) : [];
  const show = (value: string | null | undefined) => <p className={s.text}>{value || '—'}</p>;
  return <Frame>
    <Link href="/complaints">← {t('back')}</Link>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {!row ? <p>{t('loading')}</p> : <>
      <div className={s.header}>
        <div><h1>{row.number} · {row.title}</h1><p>{row.customer_name} · <span className={s.badge}>{t(`statuses.${row.status}`)}</span> · {t(`priorities.${row.priority}`)} · {categoryName(row.category)}</p></div>
        <RecordReportButton module="customers" reportKey="customers.complaints" field="complaint_id" id={row.id} permission={prefix + 'report'} label={t('pdf')} />
      </div>
      <div className={s.grid}>
        <div>{t('fields.owner')}: <strong>{row.owner_name || t('unassigned')}</strong><p>{t(`departments.${row.department}`)}</p></div>
        <div>{t('fields.receivedDate')}: {fmt.date(row.received_date)}<p>{t('fields.channel')}: {t(`channels.${row.channel}`)}</p></div>
        <div className={row.overdue ? s.error : ''}>{t('fields.resolutionDue')}: {fmt.date(row.due_date)}{row.overdue && <p>{t('overdue')}</p>}</div>
        {(row.response_due_date || row.contact || row.external_reference) && <div>
          {row.response_due_date && <p>{t('fields.responseDue')}: {fmt.date(row.response_due_date)}</p>}
          {row.contact && <p>{t('fields.contact')}: {row.contact}</p>}
          {row.external_reference && <p>{t('fields.externalReference')}: {row.external_reference}</p>}
        </div>}
      </div>
      {(next || others.length > 0) && <section className={`${s.panel} ${s.next}`}>
        {next && <><h2>{t('next.title')}</h2><p>{t(`next.${next}`)}</p></>}
        <div className={s.actions}>
          {next && <button className={`${s.button} ${s.primary}`} disabled={busy} onClick={() => open(next)}>{t(`operations.${next}`)}</button>}
          {others.map(a => <button key={a} className={s.button} disabled={busy} onClick={() => open(a)}>{t(`operations.${a}`)}</button>)}
        </div>
      </section>}
      {operation && <section className={s.panel}><h2>{t(`operations.${operation}`)}</h2><form onSubmit={submit}><fieldset disabled={busy} style={{ border: 0, padding: 0 }}>
        <div className={s.grid}>
          {operation === 'assign' && <>
            <SearchSelect title={t('form.assignee')} endpoint={`${root}/${id}/assignees`} value={fields.owner_user_id || ''} onChange={v => set('owner_user_id', v)} />
            <Field name={t('fields.department')}><select value={fields.department} onChange={e => set('department', e.target.value)}>{DEPARTMENTS.map(k => <option key={k} value={k}>{t(`departments.${k}`)}</option>)}</select></Field>
            <Field name={t('fields.resolutionDue')}><input type="date" min={row.received_date} required value={fields.due_date} onChange={e => set('due_date', e.target.value)} /></Field>
            {text('reason', t('form.assignReason'))}
          </>}
          {operation === 'investigate' && <>
            <Field name={t('investigation.finding')}><select value={fields.finding} onChange={e => set('finding', e.target.value)}>{FINDINGS.map(k => <option key={k} value={k}>{t(`findings.${k}`)}</option>)}</select></Field>
            {text('investigation', t('form.investigation'))}{text('containment', t('form.containment'), false)}
          </>}
          {operation === 'resolve' && <>{text('resolution', t('form.resolution'))}{text('implementation_evidence', t('form.evidence'))}{text('customer_response', t('form.customerResponse'))}</>}
          {operation === 'communicate' && <>
            {text('notes', t('form.notes'))}
            <label className={s.check}><input type="checkbox" checked={fields.to_customer === 'true'} onChange={e => set('to_customer', e.target.checked ? 'true' : '')} /> {t('form.toCustomer')}</label>
          </>}
          {operation === 'refer_quality' && text('notes', t('form.referral'))}
          {operation === 'link' && <>
            <Field name={t('form.referenceKind')}><select value={fields.kind} onChange={e => { set('kind', e.target.value); set('record_id', ''); }}>{KINDS.map(k => <option key={k} value={k}>{t(`kinds.${k}`)}</option>)}</select></Field>
            <SearchSelect key={fields.kind} title={t('form.reference')} endpoint={`${root}/${id}/references?kind=${fields.kind}`} value={fields.record_id || ''} onChange={v => set('record_id', v)} />
          </>}
          {operation === 'attach' && <Field name={t('form.file')}>
            <FilePicker kind="attachment" label={t('form.chooseFile')} className={s.button} hintClassName={s.muted} onFile={chosen => setFile(chosen)} />
            {file && <span>{file.name}</span>}
          </Field>}
          {!FORMS.includes(operation) && text('reason', t('form.reason'))}
        </div>
        {operation === 'investigate' && !!row.items.length && <><h3>{t('form.measurements')}</h3>{row.items.map(item => <section key={item.id} className={s.panel}>
          <h4>{named(products, item.product_key, item.product_name)}</h4>
          <Field name={t('items.confirmed')}><input type="number" min="0" max={item.delivered_quantity} step="0.001" value={findings[item.id]?.confirmed ?? ''} onChange={e => measure(item.id, { confirmed: e.target.value })} /></Field>
          {!!item.properties.length && <div className={s.tableWrap}><table className={s.table}>
            <thead><tr><th>{t('items.property')}</th><th>{t('items.expected')}</th><th>{t('items.reportedValue')}</th><th>{t('items.measured')}</th></tr></thead>
            <tbody>{item.properties.map(p => {
              const name = ar ? p.name_ar : p.name_en;
              return <tr key={p.key}><td>{name}{p.unit ? ` (${unit(p.unit)})` : ''}</td><td>{p.expected || '—'}</td><td>{p.reported || '—'}</td>
                <td><input aria-label={`${name} — ${t('items.measured')}`} maxLength={1000} value={findings[item.id]?.measured[p.key] ?? ''}
                  onChange={e => measure(item.id, { measured: { ...findings[item.id]?.measured, [p.key]: e.target.value } })} /></td></tr>;
            })}</tbody>
          </table></div>}
        </section>)}</>}
        {operation === 'items' && <ItemsEditor customerId={row.customer_id} products={products} items={drafts} onChange={setDrafts} />}
        <div className={s.actions}>
          <button className={`${s.button} ${s.primary}`} disabled={busy}>{busy ? t('form.saving') : t('form.confirm')}</button>
          <button type="button" className={s.button} onClick={() => setOperation('')}>{t('form.cancel')}</button>
        </div>
      </fieldset></form></section>}
      <section className={s.panel}><h2>{t('sections.statement')}</h2>{show(row.statement)}
        {row.items.map(item => <section key={item.id}>
          <h3>{named(products, item.product_key, item.product_name)}</h3>
          <p>{t('items.quantities', { delivered: quantity(item.delivered_quantity, item.unit), reported: quantity(item.reported_quantity, item.unit), confirmed: quantity(item.confirmed_quantity, item.unit) })}
            {item.batch_reference ? ` · ${t('items.batch')}: ${item.batch_reference}` : ''}</p>
          <p className={s.muted}>{t('items.source')}: {item.source_kind === 'manual' ? t('items.manual') : `${t(`kinds.${item.source_kind}`)} ${item.source_label ?? ''}`}</p>
          {!!item.properties.length && <div className={s.tableWrap}><table className={s.table}>
            <thead><tr><th>{t('items.property')}</th><th>{t('items.expected')}</th><th>{t('items.reportedValue')}</th><th>{t('items.measured')}</th></tr></thead>
            <tbody>{item.properties.map(p => <tr key={p.key}><td>{ar ? p.name_ar : p.name_en}{p.unit ? ` (${unit(p.unit)})` : ''}</td>
              <td>{p.expected || '—'}</td><td>{p.reported || '—'}</td><td>{p.measured || '—'}</td></tr>)}</tbody>
          </table></div>}
        </section>)}
      </section>
      <section className={s.panel}><h2>{t('sections.investigation')}</h2>
        <p>{t('investigation.finding')}: <strong>{t(`findings.${row.finding}`)}</strong></p>
        <h3>{t('investigation.investigation')}</h3>{show(row.investigation)}
        <h3>{t('investigation.containment')}</h3>{show(row.containment)}
      </section>
      <section className={s.panel}><h2>{t('sections.resolution')}</h2>
        <h3>{t('investigation.resolution')}</h3>{show(row.resolution)}
        <h3>{t('investigation.implementation_evidence')}</h3>{show(row.implementation_evidence)}
        <h3>{t('investigation.customer_response')}</h3>{show(row.customer_response)}
      </section>
      <section className={s.panel}><h2>{t('references.title')}</h2>
        <div className={s.actions}>
          {row.links.map(r => <Link className={s.button} key={r.kind + r.record_id} href={r.href}>{`${t(`kinds.${r.kind}`)} ${r.label}`}</Link>)}
          {row.attachments.map(a => <button className={s.button} key={a.id} onClick={() => download(a)}>{a.filename}</button>)}
        </div>
        {!row.links.length && !row.attachments.length && <p>{t('references.none')}</p>}
      </section>
      <Signatures resourceType="complaint" id={row.id} version={row.status} />
      <section className={s.panel}><h2>{t('history.title')}</h2>{row.events.map(e => <article key={e.id} className={s.timeline}>
        <strong>{t.has(`events.${e.action}`) ? t(`events.${e.action}`) : e.action}</strong>
        {e.actor_name ? ` · ${t('history.by', { name: e.actor_name })}` : ''} · <time>{fmt.dateTime(e.created_at)}</time>
        {describeEvent(e, t, t.has, fmt.date, ar).map((line, n) => <p key={n} className={s.text}>{line}</p>)}
      </article>)}</section>
    </>}
  </Frame>;
}
