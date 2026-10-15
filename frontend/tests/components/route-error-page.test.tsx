import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { NextIntlClientProvider } from 'next-intl';
import en from '@/i18n/locales/en/common.json';
import ar from '@/i18n/locales/ar/common.json';
import NotFound from '@/app/not-found';
import ErrorPage from '@/app/error';

const navigation = vi.hoisted(() => ({ path: '/missing-page' }));
vi.mock('next/navigation', () => ({ usePathname: () => navigation.path }));
afterEach(() => { cleanup(); navigation.path = '/missing-page'; });

it.each(['ar', 'en'])('shows a localized accessible missing page in %s', locale => {
  const common = locale === 'ar' ? ar : en;
  render(<NextIntlClientProvider locale={locale} messages={{ common }}><NotFound /></NextIntlClientProvider>);
  expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(common.errorPage.notFoundTitle);
  expect(screen.getByRole('main').getAttribute('dir')).toBe(locale === 'ar' ? 'rtl' : 'ltr');
  expect(screen.getByRole('link').getAttribute('href')).toBe('/dashboard');
});

it('keeps platform users in the platform dashboard', () => {
  navigation.path = '/platform/unknown';
  render(<NextIntlClientProvider locale="en" messages={{ common: en }}><NotFound /></NextIntlClientProvider>);
  expect(screen.getByRole('link').getAttribute('href')).toBe('/platform');
});

it('retries rendering without displaying internal error details', () => {
  const reset = vi.fn();
  render(<NextIntlClientProvider locale="en" messages={{ common: en }}><ErrorPage error={new Error('private backend details')} reset={reset} /></NextIntlClientProvider>);
  expect(screen.queryByText('private backend details')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: en.errorPage.retry }));
  expect(reset).toHaveBeenCalledOnce();
});
