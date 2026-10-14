// COMPLAINTS-001: the complaint screens in the reader's language, a history worded from its facts (never an id or a code),
// lines whose agreed values come from the customer's sales order line or sample, and the measurements of the investigation.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import type { ReactNode } from 'react';
import { afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import { loadMessages } from '@/i18n/messages';

const api = vi.hoisted(() => ({ call: vi.fn(), push: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: api.push }) }));
vi.mock('@/lib/api-client', () => ({ apiClient: api.call }));
vi.mock('@/components/layout/page-frame', () => ({ PageFrame: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
vi.mock('@/components/PermissionGuard', () => ({ PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</> }));
vi.mock('@/features/auth/permission-hooks', () => ({ usePermission: () => true }));
vi.mock('@/features/reports/RecordReportButton', () => ({ RecordReportButton: () => null }));
vi.mock('@/hooks/useFormatter', () => ({ useFormatter: () => ({ date: (v: string | null) => v ?? '—', dateTime: (v: string) => v, decimal: (v: string) => v }) }));
vi.mock('@/components/forms/UnitSelect', () => ({ UnitSelect: ({ value, onChange }: { value: string; onChange: (v: string) => void }) =>
  <select value={value} onChange={e => onChange(e.target.value)}><option value="">Choose</option><option value="kg">kg</option></select> }));
import { ComplaintCreate, ComplaintDetail } from '@/features/complaints/ComplaintsPage';

const messages: Record<string, Record<string, unknown>> = {};
beforeAll(async () => { for (const l of ['ar', 'en'] as const) messages[l] = await loadMessages(l) as Record<string, unknown>; });
const ui = (node: ReactNode, locale: 'ar' | 'en' = 'en') =>
  render(<NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">{node}</NextIntlClientProvider>);

const record = { id: 'c1', number: 'CC-2026-0001', title: 'Concern', customer_id: 'k1', customer_name: 'Customer', status: 'closed', version: 4,
  department: 'quality', priority: 'medium', category: 'quality', channel: 'email', received_date: '2026-10-11', finding: 'verified', statement: 'Customer claim',
  actions: ['reopen'], links: [], attachments: [],
  items: [{ id: 'i1', line_no: 1, product_key: 'film', product_name: 'فيلم', batch_reference: null, unit: 'kg', delivered_quantity: '500',
    reported_quantity: '120', confirmed_quantity: '80', source_kind: 'order', source_id: 'o1', source_label: 'RFS-2026-0007 / 2',
    properties: [{ key: 'thickness', name_ar: 'السماكة', name_en: 'Thickness', unit: null, expected: '40', reported: '34', measured: '35' }] }],
  events: [
    { id: 'e1', action: 'assign', notes: 'Follow up', actor_name: 'Ahmed Reviewer', created_at: '2026-10-11T10:00:00Z',
      details: { department: 'commercial', owner_name: 'Sara Owner', due_date: '2026-10-12' } },
    { id: 'e2', action: 'start', notes: 'Reviewed', actor_name: 'Ahmed Reviewer', created_at: '2026-10-11T11:00:00Z',
      details: { from_status: 'assessment', to_status: 'processing' } },
  ] };
beforeEach(() => { vi.clearAllMocks(); api.call.mockImplementation((path: string) => Promise.resolve(path.endsWith('/products') ? [] : record)); });
afterEach(cleanup);

it('words the history in Arabic from its facts, with no ids, codes or English', async () => {
  const { container } = ui(<ComplaintDetail id="c1" />, 'ar');
  await screen.findByText('CC-2026-0001 · Concern');
  const text = container.textContent ?? '';
  for (const expected of ['إسناد المسؤولية', 'المسؤول: Sara Owner', 'القسم المعالج: المبيعات وخدمة العملاء', 'موعد الحل: 2026-10-12',
    'سبب الإسناد: Follow up', 'من «قيد التقييم» إلى «قيد المعالجة»', 'السبب: Reviewed', 'بواسطة Ahmed Reviewer']) expect(text).toContain(expected);
  for (const code of ['commercial;', 'assessment', 'processing', 'assign']) expect(text).not.toContain(code);
});

it('shows the agreed, reported and measured value of each property and the confirmed quantity', async () => {
  const { container } = ui(<ComplaintDetail id="c1" />);
  await screen.findByText('CC-2026-0001 · Concern');
  const text = container.textContent ?? '';
  expect(text).toContain('Delivered 500 kg · reported 120 kg · confirmed 80 kg');
  expect(text).toContain('Sales order RFS-2026-0007 / 2');
  expect(screen.getByRole('columnheader', { name: 'Measured' })).toBeTruthy();
  expect(screen.getByRole('cell', { name: '35' })).toBeTruthy();
});

it('offers only the actions the server allows and sends a reopening with the version and reason', async () => {
  api.call.mockImplementation((path: string, options?: { method?: string }) =>
    Promise.resolve(path.endsWith('/products') ? [] : options?.method ? { ...record, status: 'processing', version: 5, actions: [] } : record));
  ui(<ComplaintDetail id="c1" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Reopen' }));
  expect(screen.queryByRole('button', { name: 'Update the investigation' })).toBeNull();
  fireEvent.change(screen.getByLabelText('Reason for the decision'), { target: { value: 'Customer reports recurrence' } });
  fireEvent.click(screen.getByRole('button', { name: 'Confirm and save' }));
  await waitFor(() => expect(api.call).toHaveBeenCalledWith('/commercial/complaints/c1/transitions',
    { method: 'POST', body: { version: 4, action: 'reopen', reason: 'Customer reports recurrence' } }));
});

it('sends the measured values and the confirmed quantity with the investigation', async () => {
  const open = { ...record, status: 'processing', actions: ['investigate'] };
  api.call.mockImplementation((path: string) => Promise.resolve(path.endsWith('/products') ? [] : open));
  ui(<ComplaintDetail id="c1" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Update the investigation' }));
  fireEvent.change(screen.getByLabelText('Findings and evidence'), { target: { value: 'Lab test' } });
  fireEvent.change(screen.getByLabelText('Thickness — Measured'), { target: { value: '36' } });
  fireEvent.change(screen.getByLabelText('Quantity confirmed as affected'), { target: { value: '90' } });
  fireEvent.click(screen.getByRole('button', { name: 'Confirm and save' }));
  await waitFor(() => expect(api.call).toHaveBeenCalledWith('/commercial/complaints/c1/investigate', expect.objectContaining({ method: 'POST',
    body: expect.objectContaining({ version: 4, items: [{ item_id: 'i1', confirmed_quantity: '90', measurements: [{ key: 'thickness', measured: '36' }] }] }) })));
});

it('takes the agreed values from the chosen sales order line and keeps the reported value typed', async () => {
  const products = [{ key: 'film', name_en: 'Film', name_ar: 'فيلم', default_unit: 'kg',
    properties: [{ key: 'thickness', name_en: 'Thickness', name_ar: 'السماكة', unit: null, kind: 'number' }] }];
  const sources = [{ kind: 'order', id: 'o1', label: 'RFS-2026-0007 / 2', product_key: 'film', unit: 'kg', quantity: '500', spec: { thickness: '40' } }];
  api.call.mockImplementation((path: string) => Promise.resolve(path.endsWith('/products') ? products : path.includes('/sources') ? sources : []));
  ui(<ComplaintCreate customerId="k1" />);
  fireEvent.click(screen.getByRole('button', { name: 'Add a product' }));
  await screen.findByRole('option', { name: 'Film' });
  fireEvent.change(screen.getByLabelText('Product'), { target: { value: 'film' } });
  fireEvent.change(await screen.findByLabelText('Agreed specification from'), { target: { value: 'order:o1' } });
  expect(screen.getByText('Agreed values taken from Sales order RFS-2026-0007 / 2')).toBeTruthy();
  expect(screen.queryByLabelText('Thickness — Agreed')).toBeNull();
  expect(screen.getByRole('cell', { name: '40' })).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Thickness — Customer report'), { target: { value: '34' } });
  expect((screen.getByLabelText('Thickness — Customer report') as HTMLInputElement).value).toBe('34');
});

it('leads with the one next step and sends contact with the customer as a reply', async () => {
  const fresh = { ...record, status: 'new', finding: 'pending', items: [], events: [], actions: ['cancel', 'assign', 'communicate'] };
  api.call.mockImplementation((path: string) => Promise.resolve(path.endsWith('/products') ? [] : fresh));
  ui(<ComplaintDetail id="c1" />);
  expect(await screen.findByText('Next step')).toBeTruthy();
  expect(screen.getByText('Assign an owner, a department and a date: this starts the processing.')).toBeTruthy();
  const buttons = screen.getAllByRole('button').map(b => b.textContent);
  expect(buttons.indexOf('Assign responsibility')).toBeLessThan(buttons.indexOf('Cancel the complaint'));
  fireEvent.click(screen.getByRole('button', { name: 'Record contact' }));
  fireEvent.change(screen.getByLabelText('What was said or done'), { target: { value: 'Acknowledged by phone' } });
  fireEvent.click(screen.getByLabelText('This was sent to the customer (it counts as the reply)'));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm and save' }));
  await waitFor(() => expect(api.call).toHaveBeenCalledWith('/commercial/complaints/c1/communications',
    { method: 'POST', body: { version: 4, notes: 'Acknowledged by phone', to_customer: true } }));
});
