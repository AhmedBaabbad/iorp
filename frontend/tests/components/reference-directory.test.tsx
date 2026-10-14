import { cleanup,fireEvent,render,screen,waitFor } from '@testing-library/react';
import { useState } from 'react';
import { afterEach,beforeEach,expect,it,vi } from 'vitest';
const mocks=vi.hoisted(()=>({api:vi.fn(),allowed:true}));
vi.mock('@/lib/api-client',()=>({apiClient:mocks.api}));
vi.mock('next-intl',()=>({useLocale:()=> 'en'}));
vi.mock('@/features/auth/permission-hooks',()=>({usePermission:()=>mocks.allowed}));
vi.mock('@/features/masterdata',()=>({ListSelect:()=>null,useListName:()=>(key:string|null|undefined)=>key??'—'}));
import { TransportSelection,type TransportValues,DriverAffiliation } from '@/features/reference-directory/DirectorySelect';
import { DirectoryPanel } from '@/features/reference-directory/DirectoryPanel';
import { ReferenceTextSelect } from '@/features/reference-directory/ReferenceTextSelect';
afterEach(cleanup);
beforeEach(()=>{mocks.api.mockReset();mocks.allowed=true;mocks.api.mockResolvedValue([]);});
function Form(){const [v,set]=useState<TransportValues>({});return <><TransportSelection value={v} onChange={set}/><output>{JSON.stringify(v)}</output></>;}

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
