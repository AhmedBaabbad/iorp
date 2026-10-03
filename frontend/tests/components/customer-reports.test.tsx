import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { loadMessages } from '@/i18n/messages';
import type { Definition } from '@/features/reports/api';
const mocks=vi.hoisted(()=>({definitions:vi.fn(),request:vi.fn(),permission:vi.fn()}));
vi.mock('@/features/auth',()=>({useAuth:()=>({hasPermission:mocks.permission})}));
vi.mock('@/features/reports/api',async original=>({...await original<object>(),getDefinitions:mocks.definitions,reportRequest:mocks.request,getLookups:()=>Promise.resolve([])}));
import { ReportForm } from '@/features/reports/ReportForm';
import { CustomerReportButtons } from '@/features/reports/CustomerReportButtons';
let messages:Record<string,unknown>;
const definition:Definition={key:'customers.customer_profile',module:'customers',title_ar:'ملف العميل',title_en:'Customer profile',
  audiences:['internal','customer'],context_fields:['customer_id'],default_orientation:'portrait',
  params_schema:{properties:{customer_id:{type:'string'},audience:{type:'string',default:'internal'}}},
  sections:[{key:'information',title_ar:'معلومات',title_en:'Information',default_enabled:true},{key:'notes',title_ar:'داخلي',title_en:'Internal notes',default_enabled:true}]};
beforeAll(async()=>{messages=await loadMessages('en');});
beforeEach(()=>{mocks.permission.mockReturnValue(true);mocks.definitions.mockResolvedValue([definition]);mocks.request.mockResolvedValue({html:'<p>Customer preview</p>'});});
afterEach(()=>{cleanup();vi.clearAllMocks();});
const ui=(node:React.ReactNode)=>render(<NextIntlClientProvider locale="en" messages={messages}>{node}</NextIntlClientProvider>);
describe('customer report audience',()=>{
  it('refreshes sections for customer audience and submits the fixed customer',async()=>{
    ui(<ReportForm definition={definition} fixedParams={{customer_id:'customer-1'}}/>);
    await screen.findByLabelText('Internal notes');
    mocks.definitions.mockResolvedValue([{...definition,sections:[definition.sections[0]]}]);
    fireEvent.change(screen.getByLabelText('Audience'),{target:{value:'customer'}});
    await waitFor(()=>expect(screen.queryByLabelText('Internal notes')).toBeNull());
    fireEvent.click(screen.getByRole('button',{name:'Preview'}));
    await waitFor(()=>expect(mocks.request).toHaveBeenCalledWith(definition.key,'preview',expect.objectContaining({customer_id:'customer-1',audience:'customer',sections:['information']})));
    expect(screen.getByTitle('Report preview').getAttribute('sandbox')).toBe('');
  });
  it('does not offer internal audience when only customer audience is allowed',()=>{
    ui(<ReportForm definition={{...definition,audiences:['customer']}} fixedParams={{customer_id:'customer-1'}}/>);
    expect(screen.queryByLabelText('Audience')).toBeNull();
    fireEvent.click(screen.getByRole('button',{name:'Preview'}));
    expect(mocks.request).toHaveBeenCalledWith(definition.key,'preview',expect.objectContaining({audience:'customer'}));
  });
  it('hides customer detail actions without permissions',()=>{
    mocks.permission.mockReturnValue(false);
    ui(<CustomerReportButtons customerId="customer-1"/>);
    expect(screen.queryByRole('button',{name:'Customer report'})).toBeNull();
    expect(screen.queryByRole('button',{name:'Order status statement'})).toBeNull();
  });
});
