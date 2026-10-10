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
  it('submits sample report filters and sections for preview and PDF',async()=>{
    const sample:Definition={...definition,key:'customers.samples_report',title_en:'Customer samples report',audiences:['internal'],
      params_schema:{properties:{sample_status:{type:'string',title_en:'Sample status',enum:['requested','evaluated']},product:{type:'string',title_en:'Product'}}},
      sections:[{key:'samples',title_ar:'العينات',title_en:'Samples',default_enabled:true},
        {key:'sample_evaluations',title_ar:'التقييمات',title_en:'Evaluations',default_enabled:true}]};
    mocks.definitions.mockResolvedValue([sample]);
    ui(<ReportForm definition={sample}/>);
    await screen.findByLabelText('Evaluations');
    fireEvent.change(screen.getByLabelText('Sample status'),{target:{value:'evaluated'}});
    fireEvent.change(screen.getByLabelText('Product'),{target:{value:'custom_product'}});
    fireEvent.click(screen.getByRole('button',{name:'Preview'}));
    await waitFor(()=>expect(mocks.request).toHaveBeenCalledWith(sample.key,'preview',expect.objectContaining({sample_status:'evaluated',product:'custom_product',sections:['samples','sample_evaluations']})));
    await waitFor(()=>expect((screen.getByRole('button',{name:/Download/}) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button',{name:/Download/}));
    await waitFor(()=>expect(mocks.request).toHaveBeenCalledWith(sample.key,'pdf',expect.objectContaining({sample_status:'evaluated',product:'custom_product'})));
  });
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
