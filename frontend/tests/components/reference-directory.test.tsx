import { cleanup,fireEvent,render,screen,waitFor } from '@testing-library/react';
import { useState } from 'react';
import { afterEach,beforeEach,expect,it,vi } from 'vitest';
const mocks=vi.hoisted(()=>({api:vi.fn(),allowed:true}));
vi.mock('@/lib/api-client',()=>({apiClient:mocks.api}));
vi.mock('next-intl',()=>({useLocale:()=> 'en',useTranslations:()=> (key:string)=>key==='actions.close'?'Close':key}));
vi.mock('@/features/auth/permission-hooks',()=>({usePermission:()=>mocks.allowed}));
vi.mock('@/features/masterdata',()=>({ListSelect:()=>null,useListName:()=>(key:string|null|undefined)=>key??'—'}));
import { TransportSelection,type TransportValues,DriverAffiliation } from '@/features/reference-directory/DirectorySelect';
import { DirectoryPanel } from '@/features/reference-directory/DirectoryPanel';
import { ReferenceTextSelect } from '@/features/reference-directory/ReferenceTextSelect';
afterEach(cleanup);
beforeEach(()=>{mocks.api.mockReset();mocks.allowed=true;mocks.api.mockResolvedValue([]);});
function Form({initial={}}:{initial?:TransportValues}){const [v,set]=useState<TransportValues>(initial);return <><TransportSelection value={v} onChange={set}/><output>{JSON.stringify(v)}</output></>;}

it('allows internal one-off entry without creating a driver or user account',async()=>{
  render(<Form/>);
  fireEvent.change(screen.getByLabelText('Driver affiliation'),{target:{value:'internal'}});
  expect(screen.getByRole('status').textContent).toContain('internal');
  await waitFor(()=>expect(mocks.api).toHaveBeenCalled());
  expect(mocks.api.mock.calls.every(([,options])=>!options?.method)).toBe(true);
});

it('selects a saved external driver and prevents changing its affiliation',async()=>{
  mocks.api.mockImplementation((path:string)=>Promise.resolve(path.includes('/drivers/')?[{id:'d1',name:'Driver',affiliation:'external'}]:[]));
  render(<Form/>);
  await screen.findByRole('option',{name:'Driver — External'});
  fireEvent.change(screen.getByLabelText('Saved driver'),{target:{value:'d1'}});
  expect((screen.getByLabelText('Driver affiliation') as HTMLSelectElement).disabled).toBe(true);
  expect(screen.getByRole('status').textContent).toContain('"driver_id":"d1"');
});

it('keeps legacy classification honest',()=>{
  render(<DriverAffiliation/>);
  expect(screen.getByText('Unclassified — legacy record')).toBeTruthy();
});

it('updates a directory record with version and without organization or audit fields',async()=>{
  mocks.api.mockImplementation((_path:string,options?:{method?:string})=>Promise.resolve(options?{}:{items:[{id:'c1',name:'Carrier',active:true,version:3,organization_id:'must-not-send'}],pages:1}));
  render(<DirectoryPanel path="/shipping/directory/carriers" kind="carriers" writePermission="shipping:directory:write"/>);
  fireEvent.click(await screen.findByRole('button',{name:'Edit'}));
  fireEvent.click(screen.getByLabelText('Active'));
  fireEvent.click(screen.getByRole('button',{name:'Save'}));
  await waitFor(()=>expect(mocks.api.mock.calls.some(([,o])=>o?.method==='PUT')).toBe(true));
  const [,options]=mocks.api.mock.calls.find(([,o])=>o?.method==='PUT')!;
  expect(options.body).toMatchObject({name:'Carrier',active:false,version:3});
  expect(options.body).not.toHaveProperty('organization_id');
});

it('does not show write actions without permission',async()=>{
  mocks.allowed=false;render(<DirectoryPanel path="/contacts" kind="contacts" writePermission="commercial:customers:update"/>);
  await waitFor(()=>expect(mocks.api).toHaveBeenCalled());
  expect(screen.queryByRole('button',{name:'Add'})).toBeNull();
});

it('keeps saved method text when the reference catalog is renamed',async()=>{
  mocks.api.mockResolvedValue([{id:'m1',name_en:'New method',name_ar:'طريقة جديدة',active:true}]);
  render(<ReferenceTextSelect list="test_method" value="Old method" onChange={()=>{}} ariaLabel="Method"/>);
  await screen.findByRole('option',{name:'Old method'});
  expect((screen.getByLabelText('Method') as HTMLSelectElement).value).toBe('Old method');
});


it('adds an external driver quickly and selects the default vehicle',async()=>{
  mocks.api.mockImplementation((path:string,options?:{method?:string})=>Promise.resolve(options?.method==='POST'
    ?{id:'quick1',name:'New driver',affiliation:'external',default_vehicle_id:'v1'}:[]));
  render(<Form/>);
  fireEvent.click(screen.getByRole('button',{name:'+ New driver'}));
  fireEvent.change(screen.getByLabelText('Name'),{target:{value:'New driver'}});
  fireEvent.change(screen.getByLabelText('National ID / Iqama'),{target:{value:'N1'}});
  fireEvent.click(screen.getByRole('button',{name:'Save and select'}));
  await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('"driver_id":"quick1"'));
  expect(screen.getByRole('status').textContent).toContain('"vehicle_id":"v1"');
  const [path,options]=mocks.api.mock.calls.find(([,o])=>o?.method==='POST')!;
  expect(path).toBe('/shipping/directory/drivers/quick');
  expect(options.body).toMatchObject({name:'New driver',identity_no:'N1',affiliation:'external'});
});

it('autofills only an empty vehicle and warns about expired licenses without blocking selection',async()=>{
  mocks.api.mockImplementation((path:string)=>Promise.resolve(path.includes('/drivers/')
    ?[{id:'d1',name:'Expired driver',affiliation:'external',default_vehicle_id:'suggested',license_expiry:'2000-01-01'}]:[]));
  render(<Form initial={{vehicle_id:'chosen'}}/>);
  await screen.findByRole('option',{name:'Expired driver — External'});
  fireEvent.change(screen.getByLabelText('Saved driver'),{target:{value:'d1'}});
  expect(screen.getByText('Driver license expired')).toBeTruthy();
  expect(screen.getByText(/"vehicle_id":"chosen"/)).toBeTruthy();
});

it('offers to select the existing driver after a duplicate identity response',async()=>{
  mocks.api.mockImplementation((path:string,options?:{method?:string})=>options?.method==='POST'
    ?Promise.reject({status:409,details:{detail:{code:'DRIVER_IDENTITY_EXISTS',existing_driver_id:'existing'}}})
    :Promise.resolve(path.includes('/drivers/')?[{id:'existing',name:'Existing driver',affiliation:'external'}]:[]));
  render(<Form/>);
  fireEvent.click(screen.getByRole('button',{name:'+ New driver'}));
  fireEvent.change(screen.getByLabelText('Name'),{target:{value:'Duplicate'}});
  fireEvent.change(screen.getByLabelText('National ID / Iqama'),{target:{value:'N1'}});
  fireEvent.click(screen.getByRole('button',{name:'Save and select'}));
  expect(await screen.findByText('This driver is already registered')).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Select it'}));
  await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('"driver_id":"existing"'));
  expect(mocks.api.mock.calls.filter(([,o])=>o?.method==='POST')).toHaveLength(1);
});


it('shows internal driver personal fields read-only from the employee record',async()=>{
  mocks.api.mockImplementation((path:string)=>Promise.resolve(path.includes('/drivers?')?{items:[{
    id:'internal',name:'Canonical employee',phone:'0551234567',email:'employee@example.com',identity_no:'EMP-1',
    affiliation:'internal',workforce_member_id:'w1',active:true,version:1}],pages:1}:[]));
  render(<DirectoryPanel path="/shipping/directory/drivers" kind="drivers" writePermission="shipping:directory:write"/>);
  fireEvent.click(await screen.findByRole('button',{name:'Edit'}));
  expect((screen.getByLabelText('Name') as HTMLInputElement).readOnly).toBe(true);
  expect((screen.getByLabelText('Phone') as HTMLInputElement).readOnly).toBe(true);
  expect((screen.getByLabelText('Email') as HTMLInputElement).readOnly).toBe(true);
  expect((screen.getByLabelText('National ID / Iqama') as HTMLInputElement).readOnly).toBe(true);
  expect(screen.getByText(/Edit them in Human resources/)).toBeTruthy();
});
