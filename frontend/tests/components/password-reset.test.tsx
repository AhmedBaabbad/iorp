import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {NextIntlClientProvider} from 'next-intl';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import en from '@/i18n/locales/en/password-reset.json';
import {ForgotPasswordPage,ResetPasswordPage} from '@/features/auth/password-reset-pages';
import {ApiClientError} from '@/lib/api-client';
const api=vi.hoisted(()=>({call:vi.fn()}));
vi.mock('@/lib/api-client',async original=>({...await original<object>(),apiClient:api.call}));
vi.mock('next/navigation',()=>({useSearchParams:()=>new URLSearchParams('token=valid-test-token-with-more-than-20-characters')}));
vi.mock('@/components/LanguageSwitcher',()=>({LanguageSwitcher:()=>null}));
vi.mock('@/components/PasswordInput',()=>({PasswordInput:(props:React.InputHTMLAttributes<HTMLInputElement>)=><input {...props} type="password"/>}));
beforeEach(()=>vi.clearAllMocks());afterEach(cleanup);
function show(reset=false){return render(<NextIntlClientProvider locale="en" messages={{passwordReset:en}}><>{reset?<ResetPasswordPage/>:<ForgotPasswordPage/>}</></NextIntlClientProvider>);}
it('sends the selected language and displays the generic response on success',async()=>{
    api.call.mockResolvedValue({});show();
    fireEvent.change(screen.getByLabelText('Email address'),{target:{value:'test@example.test'}});
    fireEvent.click(screen.getByRole('button',{name:'Send reset link'}));
    await screen.findByText('Check your email');
    expect(api.call).toHaveBeenCalledWith('/auth/forgot-password',expect.objectContaining({body:{email:'test@example.test',locale:'en'}}));
});
it('does not display success after network or rate-limit errors',async()=>{
    api.call.mockRejectedValue(new ApiClientError('Limited',429));show();
    fireEvent.change(screen.getByLabelText('Email address'),{target:{value:'test@example.test'}});
    fireEvent.click(screen.getByRole('button',{name:'Send reset link'}));
    await screen.findByText(en.forgot.rateLimit);
    expect(screen.queryByText('Check your email')).toBeNull();
});
it('retains the reset form after a transient failure rather than declaring the token invalid',async()=>{
    api.call.mockRejectedValue(new Error('Offline'));show(true);
    fireEvent.change(screen.getByLabelText('New password'),{target:{value:'StrongPassword123!'}});
    fireEvent.change(screen.getByLabelText('Confirm password'),{target:{value:'StrongPassword123!'}});
    fireEvent.click(screen.getByRole('button',{name:'Reset password'}));
    await waitFor(()=>expect(screen.getByText(en.reset.requestError)).toBeTruthy());
    expect(screen.getByLabelText('New password')).toBeTruthy();
    expect(screen.queryByText(en.reset.invalidToken)).toBeNull();
});
