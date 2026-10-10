import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import type { ReactNode } from 'react';
import { afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import { loadMessages } from '@/i18n/messages';

const api = vi.hoisted(() => ({ get: vi.fn() }));
const identity = vi.hoisted(() => ({ id: 'one', permissions: ['quality:quality_checks:read'] }));
vi.mock('@/features/auth', () => ({ useAuth: () => ({ user: { id: identity.id, full_name: 'Reviewer' }, permissions: identity.permissions, hasPermission: (code: string) => identity.permissions.includes(code) }) }));
vi.mock('@/lib/api-client', () => ({ apiClient: api.get }));
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams(), usePathname: () => '/dashboard', useRouter: () => ({ replace: vi.fn() }) }));
vi.mock('@/components/layout/page-frame', () => ({ PageFrame: ({ children, title, action }: { children: ReactNode; title: string; action: ReactNode }) => <main><h1>{title}</h1>{action}{children}</main> }));
import { DashboardWorkspace } from '@/features/dashboard/DashboardWorkspace';
let en: Awaited<ReturnType<typeof loadMessages>>, ar: Awaited<ReturnType<typeof loadMessages>>;
beforeAll(async () => { en = await loadMessages('en'); ar = await loadMessages('ar'); });
beforeEach(() => { api.get.mockReset(); identity.id = 'one'; identity.permissions = ['quality:quality_checks:read']; });
afterEach(cleanup);

it('keeps commercial follow-ups and sample decisions visible beyond the first four overview cards', async () => {
  identity.permissions = ['commercial:samples:read', 'commercial:follow_ups:read'];
  api.get.mockResolvedValue({ ...board, module: 'commercial', cards: [
    ...['new_customers', 'quotes_issued', 'orders_confirmed', 'samples_requested'].map(key => ({ key, value: '1' })),
    ...['overdue_follow_ups', 'due_today_follow_ups', 'upcoming_follow_ups', 'samples_accepted', 'samples_rejected', 'samples_pending_decision', 'samples_awaiting_evaluation']
      .map(key => ({ key, style: 'count', value: '2', href: '/samples' })),
  ] });
  render(ui());
  expect(await screen.findByText('Finally accepted samples')).toBeTruthy();
  expect(screen.getByText('Finally rejected samples')).toBeTruthy();
  expect(screen.getByText('Follow-ups remaining today')).toBeTruthy();
  expect(screen.getByRole('region', { name: 'Follow-ups and deadlines' })).toBeTruthy();
  expect(screen.getByRole('region', { name: 'Samples and customer decisions' })).toBeTruthy();
});
const board = { module: 'quality', period: '3m', start: '2026-07-01', end: '2026-10-01', cards: [
  { key: 'checks_closed', value: '123', previous: '100', spark: ['10','15','12'], href: '/quality-checks' },
  { key: 'acceptance_rate', value: '95', unit: '%', style: 'gauge', href: '/quality-checks' },
  { key: 'open_checks', value: '7', style: 'count', href: '/quality-checks' },
], series: [], breakdowns: [], rankings: [], attention: [], attention_total: 0 };
const ui = (locale = 'en', department?: 'quality') => <NextIntlClientProvider locale={locale} messages={locale === 'ar' ? ar : en} timeZone="UTC"><DashboardWorkspace department={department} /></NextIntlClientProvider>;

it('loads only authorized departments and groups workload separately from period indicators', async () => {
  api.get.mockResolvedValue(board);
  render(ui());
  expect(await screen.findByText('123')).toBeTruthy();
  expect(screen.getByText('Current workload')).toBeTruthy();
  expect(screen.getByText('95.0%')).toBeTruthy();
  expect(api.get.mock.calls.every(([path]) => path === '/quality/dashboard?period=3m' || path === '/dashboard/summary')).toBe(true);
  expect(screen.queryByRole('link', { name: 'Shipping & delivery' })).toBeNull();
});

it('clears the previous identity data immediately while the new request is pending', async () => {
  api.get.mockResolvedValue(board);
  const view = render(ui('en', 'quality'));
  await screen.findByText('123');
  identity.id = 'two';
  api.get.mockImplementation(() => new Promise(() => {}));
  view.rerender(ui('en', 'quality'));
  expect(screen.queryByText('123')).toBeNull();
});

it('shows a localized Arabic department and a recoverable load error', async () => {
  api.get.mockRejectedValue(new Error('Offline'));
  render(ui('ar', 'quality'));
  expect(await screen.findByRole('alert')).toBeTruthy();
  api.get.mockResolvedValue(board);
  fireEvent.click(screen.getByRole('button', { name: /تحديث البيانات/ }));
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
  expect(screen.getByText('الفحوص المكتملة')).toBeTruthy();
});
