import { render, screen, fireEvent, cleanup, waitFor, act } from '@testing-library/react';
import { it, expect, vi, afterEach } from 'vitest';
import { NextIntlClientProvider } from 'next-intl';
import en from '@/i18n/locales/en/platform.json';
import ar from '@/i18n/locales/ar/platform.json';
const mocks = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock('@/lib/api-client', () => ({ apiClient: mocks.api }));
import { PlatformStepUpDialog } from '@/features/platform/PlatformStepUpDialog';
import { requestStepUp } from '@/features/platform/platform-step-up';
vi.mock('@/features/platform/platform-auth-context', () => ({ usePlatformAuth: () => ({ token: 'session', logout: vi.fn() }) }));
vi.mock('@/features/platform/platform-protected-route', () => ({ PlatformProtectedRoute: ({ children }: { children: React.ReactNode }) => children }));
import { PlatformSecurityPage } from '@/features/platform/PlatformSecurityPage';
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it.each(['en', 'ar'])('verifies exact action without persisting credentials in %s', async locale => {
  const labels = locale === 'ar' ? ar : en;
  mocks.api.mockResolvedValue({ authorization: 'single-use-proof' });
  render(<NextIntlClientProvider locale={locale} messages={{ platform: labels }}><PlatformStepUpDialog /></NextIntlClientProvider>);
  let promise: Promise<string>;
  act(() => { promise = requestStepUp({ method: 'PUT', path: '/platform/organizations/id/storage', body: { quota_bytes: 12345 }, token: 'session' }); });
  fireEvent.change(screen.getByLabelText(labels.security.password), { target: { value: 'password' } });
  fireEvent.change(screen.getByLabelText(labels.security.code), { target: { value: '123456' } });
  fireEvent.click(screen.getByRole('button', { name: labels.security.verify }));
  await expect(promise!).resolves.toBe('single-use-proof');
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  expect(mocks.api).toHaveBeenCalledWith('/platform/mfa/step-up', expect.objectContaining({ body: {
    password: 'password', code: '123456', method: 'PUT', path: '/platform/organizations/id/storage', body: { quota_bytes: 12345 },
  } }));
});

it('does not authorize when verification fails and supports cancellation', async () => {
  mocks.api.mockRejectedValue(new Error('Expired session'));
  render(<NextIntlClientProvider locale="en" messages={{ platform: en }}><PlatformStepUpDialog /></NextIntlClientProvider>);
  let promise: Promise<string>;
  act(() => { promise = requestStepUp({ method: 'DELETE', path: '/platform/administrators/id' }); });
  const rejected = expect(promise!).rejects.toThrow();
  fireEvent.change(screen.getByLabelText(en.security.password), { target: { value: 'password' } });
  fireEvent.click(screen.getByRole('button', { name: en.security.verify }));
  expect(await screen.findByRole('alert')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: en.security.cancel }));
  await rejected;
  expect(screen.queryByRole('dialog')).toBeNull();
});

it.each(['en', 'ar'])('requires saved recovery codes before enrollment confirmation in %s', async locale => {
  const labels=locale==='ar'?ar:en;
  mocks.api.mockImplementation((path: string) => Promise.resolve(path.endsWith('/enroll') ? {
    secret:'SYNTHETIC-SETUP-KEY', recovery_codes:['synthetic-recovery-code'],
  } : path.endsWith('/confirm') ? { login_required:true } : {enabled:false}));
  render(<NextIntlClientProvider locale={locale} messages={{platform:labels}}><PlatformSecurityPage /></NextIntlClientProvider>);
  fireEvent.change(screen.getByLabelText(labels.security.password),{target:{value:'password'}});
  fireEvent.click(screen.getByRole('button',{name:labels.security.enroll}));
  expect(await screen.findByText('SYNTHETIC-SETUP-KEY')).toBeTruthy();
  expect((screen.getByRole('button',{name:labels.security.verify}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText(labels.security.saved));
  fireEvent.change(screen.getByLabelText(labels.security.code),{target:{value:'123456'}});
  fireEvent.click(screen.getByRole('button',{name:labels.security.verify}));
  await screen.findByText(labels.security.loginAgain);
  expect(screen.queryByText('SYNTHETIC-SETUP-KEY')).toBeNull();
  expect(screen.queryByText('synthetic-recovery-code')).toBeNull();
  expect(mocks.api).toHaveBeenCalledWith('/platform/mfa/confirm',expect.objectContaining({body:{code:'123456',saved_recovery_codes:true}}));
});
