import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import type { ReactNode } from 'react';
import { afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import { loadMessages } from '@/i18n/messages';

const api = vi.hoisted(() => ({ products: vi.fn(), create: vi.fn(), get: vi.fn(), update: vi.fn() }));
const access = vi.hoisted(() => ({ allowed: true }));
vi.mock('@/features/auth', () => ({ useAuth: () => ({ hasPermission: () => access.allowed }) }));
vi.mock('@/features/samples/api/samples-api', () => ({ getSampleProducts: api.products, createSample: api.create, getSampleById: api.get, updateSample: api.update }));
// ARCH-PAGE-001: the customer is chosen with the picker (a server search); here it chooses the one customer.
vi.mock('@/features/customers', async () => {
  const { useEffect } = await import('react');
  return { CustomerPicker: ({ value, onChange }: { value: string; onChange: (id: string) => void }) => {
    useEffect(() => { if (!value) onChange('c1'); }, [value, onChange]);
    return <select aria-label="Customer" value={value} onChange={(e) => onChange(e.target.value)}><option value="c1">Customer (C1)</option></select>;
  } };
});
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace: vi.fn() }), useParams: () => ({ id: 's1' }) }));
vi.mock('@/components/layout/page-frame', () => ({ PageFrame: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
import { SampleForm } from '@/features/samples/components/SampleForm';
import { SampleEditForm } from '@/features/samples/components/SampleEditForm';

let messages: Awaited<ReturnType<typeof loadMessages>>;
beforeAll(async () => { messages = await loadMessages('en'); });
afterEach(cleanup);
const definition = { key: 'generic', name_ar: 'منتج', name_en: 'Generic product', active: true, default_unit: 'kg', properties: [
  { key: 'dimension', name_ar: 'المقاس', name_en: 'Dimension', kind: 'number', required: true, unit: 'mm', options: [] },
] };
const saved = { id: 's1', sample_code: 'RFS-001', product_type: 'generic', status: 'requested', is_sample_requested: false,
  request_date: '2026-10-06T10:00:00Z', requested_spec_json: { dimension: 9 }, property_values: { dimension: 9 }, product_definition: definition, notes: 'Original' };
beforeEach(() => { access.allowed = true; vi.clearAllMocks(); api.products.mockResolvedValue([definition]); api.get.mockResolvedValue(saved); api.create.mockResolvedValue(saved); api.update.mockResolvedValue(saved); });
function ui(node: ReactNode) { return render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">{node}</NextIntlClientProvider>); }

it('restricts lifecycle choices and disables decisions without action permissions', async () => {
  access.allowed = false;
  const { container } = ui(<SampleEditForm />);
  await screen.findByLabelText('Dimension');
  const status = container.querySelector('option[value="requested"]')!.parentElement as HTMLSelectElement;
  expect(Array.from(status.options).map(option => option.value)).toEqual(['requested']);
  const decision = container.querySelector('option[value="accepted"]')!.parentElement as HTMLSelectElement;
  expect(decision.disabled).toBe(true);
});

it('submits typed property values from the creation screen without a JSON editor', async () => {
  const { container } = ui(<SampleForm />);
  const option = await screen.findByRole('option', { name: 'Generic product' });
  fireEvent.change(option.parentElement!, { target: { value: 'generic' } });
  fireEvent.change(screen.getByLabelText('Dimension'), { target: { value: '14.25' } });
  fireEvent.submit(container.querySelector('form')!);
  await waitFor(() => expect(api.create).toHaveBeenCalled());
  expect(api.create.mock.calls[0][0]).toMatchObject({ customer_id: 'c1', product_type: 'generic', property_values: { dimension: 14.25 } });
  expect(api.create.mock.calls[0][0]).not.toHaveProperty('requested_spec_json');
  expect(container.querySelectorAll('textarea')).toHaveLength(1); // notes only
});

it('loads saved values and sends changed specifications on edit', async () => {
  const { container } = ui(<SampleEditForm />);
  const field = await screen.findByLabelText('Dimension');
  expect((field as HTMLInputElement).value).toBe('9');
  fireEvent.change(field, { target: { value: '10' } });
  fireEvent.submit(container.querySelector('form')!);
  await waitFor(() => expect(api.update).toHaveBeenCalledWith('s1', expect.objectContaining({ product_type: 'generic', property_values: { dimension: 10 } })));
});

it('keeps legacy specifications out of unrelated edits', async () => {
  api.get.mockResolvedValue({ ...saved, product_type: 'Old label', product_definition: null, property_values: { old: 'Historical value' } });
  const { container } = ui(<SampleEditForm />);
  await screen.findByText('Historical value');
  fireEvent.change(container.querySelector('textarea')!, { target: { value: 'New notes' } });
  fireEvent.submit(container.querySelector('form')!);
  await waitFor(() => expect(api.update).toHaveBeenCalled());
  const body = api.update.mock.calls[0][1];
  expect(body.notes).toBe('New notes');
  expect(body).not.toHaveProperty('property_values');
  expect(body).not.toHaveProperty('product_type');
});

it('loads the saved template for an inactive product absent from the choices', async () => {
  api.products.mockResolvedValue([]);
  api.get.mockResolvedValue({ ...saved, product_definition: { ...definition, active: false } });
  ui(<SampleEditForm />);
  expect((await screen.findByLabelText('Dimension') as HTMLInputElement).value).toBe('9');
});

it('uses the shared unit choices when requesting a physical sample', async () => {
  const { container } = ui(<SampleForm />);
  const option = await screen.findByRole('option', { name: 'Generic product' });
  fireEvent.change(option.parentElement!, { target: { value: 'generic' } });
  fireEvent.click(screen.getByRole('checkbox'));
  const unit = container.querySelector('select[aria-label="Unit"]') as HTMLSelectElement;
  expect(unit).toBeTruthy();
  expect(unit.value).toBe('kg');
  expect(unit.querySelector('option[value="mm"]')).toBeTruthy();
  fireEvent.change(unit, { target: { value: 'mm' } });
  fireEvent.submit(container.querySelector('form')!);
  await waitFor(() => expect(api.create).toHaveBeenCalled());
  expect(api.create.mock.calls[0][0].unit).toBe('mm');
});

it('preserves an older unit while offering shared choices on edit', async () => {
  api.get.mockResolvedValue({ ...saved, is_sample_requested: true, requested_sample_quantity: '2', unit: 'Legacy unit' });
  const { container } = ui(<SampleEditForm />);
  await screen.findByLabelText('Dimension');
  const unit = container.querySelector('select[aria-label="Unit"]') as HTMLSelectElement;
  expect(unit.value).toBe('Legacy unit');
  expect(unit.querySelector('option[value="kg"]')).toBeTruthy();
});
