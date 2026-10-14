import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {it,expect,vi,afterEach} from 'vitest';
import {NextIntlClientProvider} from 'next-intl';
import en from '@/i18n/locales/en/profile.json';
import ar from '@/i18n/locales/ar/profile.json';
const mocks=vi.hoisted(()=>({api:vi.fn()}));
vi.mock('@/lib/api-client',async importOriginal=>({...await importOriginal<typeof import('@/lib/api-client')>(),apiClient:mocks.api}));
import {ApiClientError} from '@/lib/api-client';
import {EmailChangeForm} from '@/features/auth/email-change-form';
afterEach(()=>{cleanup();vi.clearAllMocks();});
it.each(['ar','en'])('requires owner credentials and displays both verification inputs in %s',async locale=>{
 mocks.api.mockResolvedValue({});const labels=locale==='ar'?ar.emailChange:en.emailChange;
 render(<NextIntlClientProvider locale={locale} messages={{profile:locale==='ar'?ar:en}}><EmailChangeForm/></NextIntlClientProvider>);
 fireEvent.change(screen.getByLabelText(labels.email),{target:{value:'new@example.com'}});
 fireEvent.change(screen.getByLabelText(labels.password),{target:{value:'current-password'}});
 fireEvent.click(screen.getByRole('button',{name:labels.request}));
 await screen.findByLabelText(labels.oldCode);
 expect(screen.getByLabelText(labels.newCode)).toBeTruthy();
 await waitFor(()=>expect(mocks.api).toHaveBeenCalledWith('/auth/me/email-change',expect.objectContaining({headers:{'Accept-Language':locale},body:{email:'new@example.com',current_password:'current-password'}})));
 expect(screen.queryByLabelText(labels.password)).toBeNull();
});

it.each(['CURRENT_PASSWORD_INCORRECT','EMAIL_UNCHANGED','EMAIL_DELIVERY_FAILED'])('explains %s instead of hiding the cause',async code=>{
 mocks.api.mockRejectedValue(new ApiClientError('Request failed',400,{code}));
 render(<NextIntlClientProvider locale="en" messages={{profile:en}}><EmailChangeForm/></NextIntlClientProvider>);
 fireEvent.change(screen.getByLabelText(en.emailChange.email),{target:{value:'new@example.com'}});
 fireEvent.change(screen.getByLabelText(en.emailChange.password),{target:{value:'password'}});
 fireEvent.click(screen.getByRole('button',{name:en.emailChange.request}));
 expect((await screen.findByRole('alert')).textContent).toBe(en.emailChange.errors[code as keyof typeof en.emailChange.errors]);
});
