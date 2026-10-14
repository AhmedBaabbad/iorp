import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {NextIntlClientProvider} from 'next-intl';
import en from '@/i18n/locales/en/administration.json';
import ar from '@/i18n/locales/ar/administration.json';
const mocks=vi.hoisted(()=>({get:vi.fn(),catalog:vi.fn(),assign:vi.fn(),remove:vi.fn(),scope:vi.fn(),allowed:true}));
vi.mock('@/features/auth',()=>({usePermission:()=>mocks.allowed}));
vi.mock('@/features/admin-permissions/api/admin-permissions-api',()=>({listAdminPermissions:mocks.catalog}));
vi.mock('@/features/admin-roles/api/admin-roles-api',()=>({getAdminRole:mocks.get,assignAdminPermissionToRole:mocks.assign,removeAdminPermissionFromRole:mocks.remove,updateAdminRolePermissionScope:mocks.scope}));
import {AdminRolePermissionsManager} from '@/features/admin-roles/components/AdminRolePermissionsManager';
const permission={code:'commercial:orders:read',name:'English fallback',name_en:'Read orders',name_ar:'قراءة الطلبات',description_en:'View customer orders',description_ar:'عرض أوامر العملاء',scopable:true};
function show(locale='en'){return render(<NextIntlClientProvider locale={locale} messages={{administration:locale==='ar'?ar:en,messages:{}}}><AdminRolePermissionsManager roleId="r1"/></NextIntlClientProvider>);}
afterEach(cleanup);
beforeEach(()=>{vi.clearAllMocks();mocks.allowed=true;mocks.get.mockResolvedValue({is_editable:true,permissions:[]});mocks.catalog.mockResolvedValue([{module:'commercial',module_name_en:'Commercial',module_name_ar:'التجاري',permissions:[permission]}]);mocks.assign.mockResolvedValue({});});
it.each(['ar','en'])('uses catalog names and explanations in %s',async locale=>{show(locale);expect(await screen.findByText(locale==='ar'?'قراءة الطلبات':'Read orders')).toBeTruthy();expect(screen.getByText(locale==='ar'?'عرض أوامر العملاء':'View customer orders')).toBeTruthy();expect(screen.queryByText('English fallback')).toBeNull();});
it('searches bilingual labels and filters granted permissions',async()=>{show();await screen.findByText('Read orders');fireEvent.change(screen.getByRole('textbox'),{target:{value:'قراءة'}});expect(screen.getByText('Read orders')).toBeTruthy();fireEvent.change(screen.getByLabelText('Permission status'),{target:{value:'assigned'}});expect(screen.getByText('No permissions match your search')).toBeTruthy();});
it('keeps protected roles disabled even when the caller omits readOnly',async()=>{mocks.get.mockResolvedValue({is_editable:false,permissions:[]});show();await screen.findByText('Read orders');expect((screen.getByLabelText('Read orders') as HTMLInputElement).disabled).toBe(true);expect(mocks.assign).not.toHaveBeenCalled();});
it('submits the canonical code rather than the translated label',async()=>{show();await screen.findByText('Read orders');fireEvent.click(screen.getByLabelText('Read orders'));await waitFor(()=>expect(mocks.assign).toHaveBeenCalledWith('r1',{permission_code:'commercial:orders:read'}));});
it('disables writes without permission',async()=>{mocks.allowed=false;show();await screen.findByText('Read orders');expect((screen.getByLabelText('Read orders') as HTMLInputElement).disabled).toBe(true);});
