// PROD-REPORT-001: report form from definitions, localized messages, and the branding editor.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import type { ReactNode } from 'react';
import { afterEach, beforeAll, beforeEach, describe, it, expect, vi } from 'vitest';
import { loadMessages } from '@/i18n/messages';
import type { Definition } from '@/features/reports/api';

const mocks = vi.hoisted(() => ({ request: vi.fn(), api: vi.fn() }));
vi.mock('@/features/auth', () => ({ useAuth: () => ({ token: 'test-token', hasPermission: () => true }) }));
vi.mock('@/features/reports/api', async original => ({ ...await original<object>(), reportRequest: mocks.request, getDefinitions: () => Promise.resolve([]), getLookups: () => Promise.resolve([]) }));
vi.mock('@/lib/api-client', async original => ({ ...await original<object>(), apiClient: mocks.api }));

import { ReportForm } from '@/features/reports/ReportForm';
import { BrandingEditor } from '@/features/organization-profile/BrandingEditor';

let en: Record<string, unknown>;
let ar: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages('en') as Record<string, unknown>; ar = await loadMessages('ar') as Record<string, unknown>; });
afterEach(cleanup);
beforeEach(() => { mocks.request.mockReset(); mocks.api.mockReset(); });
const definition: Definition = { key: 'production.orders_summary', title_ar: 'ملخص الإنتاج', title_en: 'Summary', default_orientation: 'landscape',
  params_schema: { properties: { date_from: { type: 'string', format: 'date', title_ar: 'من تاريخ', title_en: 'From date' }, grouping: { type: 'string', enum: ['none', 'month'], default: 'none' } }, required: [] },
  sections: [{ key: 'orders', title_ar: 'الأوامر', title_en: 'Orders', default_enabled: true }] };
const ui = (node: ReactNode, lang: 'ar' | 'en' = 'ar') => render(<NextIntlClientProvider locale={lang} messages={lang === 'ar' ? ar : en} timeZone="UTC">{node}</NextIntlClientProvider>);

describe('report form', () => {
  it('builds fields from the definition and previews server HTML in a sandbox', async () => {
    mocks.request.mockResolvedValue({ html: '<html dir="rtl"><body>اختبار</body></html>' }); ui(<ReportForm definition={definition} />);
    fireEvent.change(screen.getByLabelText('من تاريخ'), { target: { value: '2026-10-01' } });
    expect(screen.getByRole('option', { name: 'دون تجميع' })).toBeTruthy();  // enum values come from the locale files
    fireEvent.click(screen.getByRole('button', { name: 'معاينة' }));
    await waitFor(() => expect(mocks.request).toHaveBeenCalledWith(definition.key, 'preview', expect.objectContaining({ date_from: '2026-10-01', sections: ['orders'], orientation: 'landscape', lang: 'ar' })));
    const frame = await screen.findByTitle('معاينة التقرير'); expect(frame.getAttribute('sandbox')).toBe(''); expect(frame.getAttribute('srcdoc')).toContain('dir="rtl"');
  });

  it('sends section selection and language for PDF', async () => {
    mocks.request.mockResolvedValue({}); ui(<ReportForm definition={definition} />, 'en');
    fireEvent.click(screen.getByLabelText('Orders')); fireEvent.change(screen.getByLabelText('Language'), { target: { value: 'ar' } }); fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }));
    await waitFor(() => expect(mocks.request).toHaveBeenCalledWith(definition.key, 'pdf', expect.objectContaining({ sections: [], lang: 'ar' })));
  });

  it('shows a useful row-limit error in Arabic and English, never the raw code', async () => {
    mocks.request.mockRejectedValue(new Error('REPORT_ROW_LIMIT_NARROW_FILTERS')); ui(<ReportForm definition={definition} />);
    fireEvent.click(screen.getByRole('button', { name: 'معاينة' }));
    expect((await screen.findByRole('alert')).textContent).toBe('عدد الصفوف كبير. ضيّق نطاق عوامل التصفية.');
    cleanup();
    ui(<ReportForm definition={definition} />, 'en');
    fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
    expect((await screen.findByRole('alert')).textContent).toBe('The report has too many rows. Narrow the filters.');
  });

  it('falls back to a general message for an unknown failure', async () => {
    mocks.request.mockRejectedValue(new Error('HTTP_500')); ui(<ReportForm definition={definition} />, 'en');
    fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
    expect((await screen.findByRole('alert')).textContent).toBe('The report could not be created. Check your connection and permissions.');
  });
});

describe('branding editor', () => {
  it('loads identity, reflects changes in the preview, then saves only editable fields', async () => {
    mocks.api.mockResolvedValue({ name: 'Company', legal_name_ar: 'الشركة', logo_data_uri: 'data:image/png;base64,AA==' }); ui(<BrandingEditor />);
    const field = await screen.findByLabelText('الاسم القانوني بالعربية'); await waitFor(() => expect((field as HTMLInputElement).value).toBe('الشركة'));
    fireEvent.change(field, { target: { value: 'هوية جديدة' } }); expect(screen.getAllByText('هوية جديدة').length).toBeGreaterThan(0);  // header and footer of the preview
    fireEvent.click(screen.getByRole('button', { name: 'حفظ الهوية' }));
    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith('/organization/branding', expect.objectContaining({ method: 'PUT', body: expect.objectContaining({ legal_name_ar: 'هوية جديدة' }) })));
  });

  it('rejects an unsupported logo before upload and uploads a valid one through the API client', async () => {
    const images = { types: ['image/png', 'image/jpeg', 'image/webp'], max_bytes: { 'image/png': 1048576, 'image/jpeg': 1048576, 'image/webp': 1048576 } };
    const policy = { logo: images, attachment: images };
    mocks.api.mockImplementation((path: string) => Promise.resolve(path === '/system/file-policy' ? policy : { name: 'Company' }));
    ui(<BrandingEditor />, 'en');
    const input = await screen.findByLabelText('Upload secondary logo');
    await screen.findByText(/PNG, JPEG, WebP up to 1 MB/);  // the limits come from the one server policy
    fireEvent.change(input, { target: { files: [new File(['<svg/>'], 'x.svg', { type: 'image/svg+xml' })] } });
    expect((await screen.findByRole('alert')).textContent).toBe('This file type is not accepted. Allowed: PNG, JPEG, WebP.');
    fireEvent.change(input, { target: { files: [new File([new Uint8Array([137, 80, 78, 71])], 'logo.png', { type: 'image/png' })] } });
    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith('/organization/branding/logo?secondary=true', expect.objectContaining({ method: 'POST', body: expect.any(FormData) })));
  });
});
