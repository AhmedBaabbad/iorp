/**
 * A history entry as sentences in the reader's language: its stored facts by name (department, owner, dates, statuses,
 * references), then what the person wrote. Nothing is shown as a code or an id. Entries of removed steps (assessment,
 * a waiting reason) still read.
 */
import type { ComplaintEvent } from './api';

type T = (key: string, values?: Record<string, string | number>) => string;
type Has = (key: string) => boolean;

const TRANSITIONS = ['assess', 'start', 'request_close', 'approve_close', 'return', 'reopen', 'cancel'];
const FIELDS = ['investigation', 'containment', 'waiting_reason', 'resolution', 'implementation_evidence', 'customer_response'];
const REASONS = ['assign', 'note', 'response', 'refer_quality'];

const text = (value: unknown) => (value === null || value === undefined ? '' : String(value));

export function describeEvent(event: ComplaintEvent, t: T, has: Has, date: (value: string) => string, ar: boolean): string[] {
  const d = event.details ?? {};
  const word = (group: string, key: unknown) => (has(`${group}.${text(key)}`) ? t(`${group}.${text(key)}`) : text(key));
  const lines: string[] = [];
  if (event.action === 'assign') {
    lines.push(t('history.owner', { name: text(d.owner_name) || '—' }), t('history.department', { name: word('departments', d.department) }));
    if (d.due_date) lines.push(t('history.due', { date: date(text(d.due_date)) }));
    if (d.previous_owner_name && d.previous_owner_name !== d.owner_name) lines.push(t('history.previousOwner', { name: text(d.previous_owner_name) }));
    if (d.from_status) lines.push(t('history.fromTo', { from: word('statuses', d.from_status), to: word('statuses', d.to_status) }));
  } else if (TRANSITIONS.includes(event.action) && d.from_status) {
    lines.push(t('history.fromTo', { from: word('statuses', d.from_status), to: word('statuses', d.to_status) }));
  } else if (event.action === 'created' && d.category) {
    lines.push(t('history.created', { category: word('categories', d.category), priority: word('priorities', d.priority), channel: word('channels', d.channel) }));
  } else if (event.action === 'investigate' || event.action === 'resolve') {
    if (d.finding) lines.push(t('history.finding', { value: word('findings', d.finding) }));
    const fields = (d.fields ?? {}) as Record<string, unknown>;
    for (const key of FIELDS) if (fields[key]) lines.push(t('history.field', { field: t(`investigation.${key}`), value: text(fields[key]) }));
    for (const item of (d.items ?? []) as Record<string, unknown>[]) {
      const measured = ((ar ? item.measured : item.measured_en) ?? {}) as Record<string, unknown>;
      const values = Object.entries(measured).map(([name, value]) => `${name} ${text(value)}`).join(ar ? '، ' : ', ');
      if (values) lines.push(t('history.measured', { product: text(item.product), values }));
      if (item.confirmed_quantity) lines.push(t('history.confirmed', { product: text(item.product), quantity: text(item.confirmed_quantity) }));
    }
    const previous = (d.previous ?? {}) as Record<string, unknown>;
    for (const key of FIELDS) if (previous[key]) lines.push(t('history.previous', { field: t(`investigation.${key}`), value: text(previous[key]) }));
  } else if (event.action === 'linked' && d.kind) {
    lines.push(t('history.reference', { kind: word('kinds', d.kind), label: text(d.label) }));
  } else if (event.action === 'refer_quality' && d.ncr_number) {
    lines.push(t('history.ncr', { number: text(d.ncr_number) }));
  } else if (event.action === 'attachment' && d.filename) {
    lines.push(t('history.file', { name: text(d.filename) }));
  } else if (event.action === 'items_updated') {
    lines.push(t('history.lines', { count: Number(d.lines ?? 0) }));
  }
  if (event.notes) {
    const reason = REASONS.includes(event.action) ? event.action : 'other';
    lines.push(`${t(`history.reasons.${reason}`)}: ${event.notes}`);
  }
  return lines;
}
