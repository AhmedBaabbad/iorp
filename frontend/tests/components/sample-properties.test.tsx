import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import { useState } from 'react';
import { afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import { loadMessages } from '@/i18n/messages';
import { SampleProductFields, SamplePropertyValues } from '@/features/samples/components/SampleProperties';
import type { RequestedSpec, SampleProductDefinition } from '@/features/samples/types';

const api = vi.hoisted(() => ({ products: vi.fn(), changed: vi.fn(), ready: vi.fn() }));
vi.mock('@/features/samples/api/samples-api', () => ({ getSampleProducts: api.products }));
let messages: Awaited<ReturnType<typeof loadMessages>>;
beforeAll(async () => { messages = await loadMessages('en'); });
beforeEach(() => { vi.clearAllMocks(); api.products.mockResolvedValue([product, other]); });
afterEach(cleanup);
const product: SampleProductDefinition = { key: 'custom', name_ar: 'منتج', name_en: 'Custom product', active: true, default_unit: 'roll', properties: [
  { key: 'size', name_ar: 'المقاس', name_en: 'Size', kind: 'number', unit: 'mm', required: true, options: null },
  { key: 'finish', name_ar: 'التشطيب', name_en: 'Finish', kind: 'choice', unit: null, required: false, options: [{ value: 'smooth', label_ar: 'ناعم', label_en: 'Smooth' }] },
  { key: 'memo', name_ar: 'وصف', name_en: 'Description', kind: 'text', unit: null, required: false, options: null },
] };
const other: SampleProductDefinition = { ...product, key: 'other', name_en: 'Other product', default_unit: 'kg', properties: [] };
function Editor({ initial = {}, selected = '', unchanged = false }: { initial?: RequestedSpec; selected?: string; unchanged?: boolean }) {
  const [key, setKey] = useState(selected), [values, setValues] = useState(initial);
  return <SampleProductFields productKey={key} values={values} disabled={false} unchanged={unchanged}
    onReady={api.ready} onChange={(k, v, unit) => { setKey(k); setValues(v); api.changed(k, v, unit); }} />;
}
function ui(node: React.ReactNode) { return render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">{node}</NextIntlClientProvider>); }

it('loads arbitrary Master Data fields and emits typed numbers and choice values', async () => {
  const { container } = ui(<Editor />);
  await screen.findByRole('option', { name: 'Custom product' });
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'custom' } });
  const size = screen.getByLabelText('Size') as HTMLInputElement;
  expect(size.type).toBe('number'); expect(size.required).toBe(true);
  fireEvent.change(size, { target: { value: '12.5' } });
  fireEvent.change(screen.getByLabelText('Finish'), { target: { value: 'smooth' } });
  fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Trial' } });
  expect(api.changed).toHaveBeenLastCalledWith('custom', { size: 12.5, finish: 'smooth', memo: 'Trial' }, undefined);
  expect(container.querySelector('textarea')).toBeNull();
  expect(container.textContent).not.toContain('requested_spec_json');
});

it('clears incompatible property values when selecting another product', async () => {
  ui(<Editor selected="custom" initial={{ size: 5 }} />);
  await screen.findByLabelText('Size');
  fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'other' } });
  expect(api.changed).toHaveBeenLastCalledWith('other', {}, 'kg');
  expect(screen.queryByLabelText('Size')).toBeNull();
});

it('restores saved fields and preserves historical nested values read-only', async () => {
  ui(<Editor selected="custom" initial={{ size: 5, historical: { note: 'Original value' } }} unchanged />);
  expect((await screen.findByLabelText('Size') as HTMLInputElement).value).toBe('5');
  expect(screen.getByText('Original value')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Size'), { target: { value: '6' } });
  expect(api.changed).toHaveBeenLastCalledWith('custom', { size: 6, historical: { note: 'Original value' } }, undefined);
});

it('does not permit free text products when the catalog is empty', async () => {
  api.products.mockResolvedValue([]);
  const { container } = ui(<Editor />);
  await waitFor(() => expect((screen.getByRole('combobox') as HTMLSelectElement).disabled).toBe(false));
  expect(screen.getAllByRole('option')).toHaveLength(1);
  expect(api.ready).toHaveBeenLastCalledWith(false);
  expect(container.querySelector('input')).toBeNull();
});

it('blocks new specifications on catalog failure and supports retry', async () => {
  api.products.mockRejectedValueOnce(new Error('offline'));
  ui(<Editor />);
  await screen.findByRole('alert');
  expect(api.ready).toHaveBeenLastCalledWith(false);
  fireEvent.click(screen.getByRole('button'));
  await screen.findByRole('option', { name: 'Custom product' });
  expect(screen.queryByRole('alert')).toBeNull();
});

it('renders labels, units, choice labels and nested legacy values without raw JSON', () => {
  const { container } = ui(<SamplePropertyValues definition={product} values={{ size: 12, finish: 'smooth', old: { note: ['Legacy value'] } }} />);
  expect(screen.getByText('Size (mm)')).toBeTruthy();
  expect(screen.getByText('Smooth')).toBeTruthy();
  expect(screen.getByText('Legacy value')).toBeTruthy();
  expect(container.querySelector('pre, textarea')).toBeNull();
});

it('uses Arabic Master Data labels and choice labels', async () => {
  const ar = await loadMessages('ar');
  render(<NextIntlClientProvider locale="ar" messages={ar} timeZone="UTC"><div dir="rtl">
    <SamplePropertyValues definition={product} values={{ size: 12, finish: 'smooth' }} />
  </div></NextIntlClientProvider>);
  expect(screen.getByText('المقاس (mm)')).toBeTruthy();
  expect(screen.getByText('ناعم')).toBeTruthy();
});
