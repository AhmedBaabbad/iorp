import {useState,type ReactNode} from "react";
import Link from "next/link";
import {cleanup,fireEvent,render,screen,waitFor,within} from "@testing-library/react";
import {NextIntlClientProvider} from "next-intl";
import {afterEach,beforeAll,beforeEach,expect,it,vi} from "vitest";
import {loadMessages} from "@/i18n/messages";
import {refreshCatalog,useProducts} from "@/features/masterdata/catalog";
import {ProductSelect} from "@/features/masterdata/components/ProductSelect";
import {ListSelect} from "@/features/masterdata/components/ListSelect";
import {CustomerFields} from "@/features/customers/CustomerFields";
import {defaultCustomerFormValues} from "@/features/customers/customer-form";
import {ShipmentForm} from "@/features/shipments/components/ShipmentForm";
import {QuoteForm} from "@/features/quotes/components/QuoteForm";
import {CommercialOrderForm} from "@/features/commercial-orders/components/CommercialOrderForm";
import {SpecificationForm} from "@/features/quality-specifications/components/SpecificationForm";
import {useUnsavedFormChanges} from "@/hooks/useUnsavedChangesGuard";
import type {ListItem,Product,ProductInput} from "@/features/masterdata/types";

const api=vi.hoisted(()=>({request:vi.fn()}));
const nav=vi.hoisted(()=>({push:vi.fn(),replace:vi.fn()}));
const permission=vi.hoisted(()=>({allowed:true}));
vi.mock("@/lib/api-client",async original=>({...await original<object>(),apiClient:api.request}));
vi.mock("next/navigation",()=>({useRouter:()=>nav,useSearchParams:()=>new URLSearchParams(),usePathname:()=>"/"}));
vi.mock("@/features/auth/permission-hooks",()=>({usePermission:()=>permission.allowed,useHasAnyPermission:()=>permission.allowed}));
vi.mock("@/features/auth",()=>({useAuth:()=>({user:{timezone:"UTC"}})}));
vi.mock("@/features/customers",()=>({CustomerPicker:({onChange}:{onChange:(id:string)=>void})=><button type="button" onClick={()=>onChange("customer")}>Pick customer</button>,customersByIds:()=>Promise.resolve([])}));
vi.mock("@/components/layout/page-frame",()=>({PageFrame:({title,action,children}:{title:string;action?:ReactNode;children:ReactNode})=><main><h1>{title}</h1>{action}{children}</main>}));
let messages:Record<string,unknown>,products:Product[],items:ListItem[];
beforeAll(async()=>{messages=await loadMessages("en") as Record<string,unknown>;});
beforeEach(async()=>{
  permission.allowed=true;nav.push.mockReset();nav.replace.mockReset();window.history.replaceState(null,"","/");products=[];
  items=[{id:"sa",list:"country",key:"sa",name_ar:"السعودية",name_en:"Saudi Arabia",parent_key:null,active:true,sort_order:0}];
  api.request.mockReset().mockImplementation((path:string,options?:{method?:string;body?:unknown})=>{
    if(path==="/masterdata/products"&&options?.method==="POST"){
      const body=options.body as ProductInput;const product={...body,id:"new-product",key:body.key||"new_product",code:"PRD-1",actions:["edit"],created_at:"",updated_at:""} as Product;
      products.push(product);return Promise.resolve(product);
    }
    if(path.startsWith("/masterdata/products"))return Promise.resolve(products);
    if(path.startsWith("/masterdata/lists/")&&options?.method==="POST"){
      const item={...(options.body as ListItem),id:"new-city",key:"new_city",list:"city",active:true,sort_order:0} as ListItem;items.push(item);return Promise.resolve(item);
    }
    if(path.startsWith("/masterdata/lists"))return Promise.resolve(items);
    if(path==="/masterdata/settings")return Promise.resolve({vat_rate:"15",default_currency:"SAR"});
    if(path.includes("quote-settings/validity"))return Promise.resolve({quote_validity_days:10,document_language:"en"});
    if(path.includes("/lookups/customers"))return Promise.resolve([{id:"customer",name:"Customer",customer_code:"C1"}]);
    if(path==="/quality/quality-test-parameters"&&options?.method==="POST")return Promise.resolve({...options.body as object,id:"parameter",is_active:true});
    return Promise.resolve([]);
  });
  await refreshCatalog();
});
afterEach(cleanup);
const ui=(node:ReactNode)=>render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">{node}</NextIntlClientProvider>);
function Customer(){const[values,set]=useState({...defaultCustomerFormValues,country:"sa"});return <form><CustomerFields values={values} onChange={patch=>set(old=>({...old,...patch}))} disabled={false} canAssignOwner={false} eligibleOwners={[]} loadingOwners={false}/></form>;}

it.each(["customer","shipment"])("adds a city inside the %s form without losing typed data and updates other selectors",async(form)=>{
  function Observer(){const[value,set]=useState("");return <ListSelect list="city" parent="sa" ariaLabel="Other city selector" value={value} onChange={set}/>;}
  ui(<>{form==="customer"?<Customer/>:<ShipmentForm/>}<Observer/></>);
  if(form==="shipment"){
    fireEvent.click(screen.getByLabelText("Unregistered customer"));
    fireEvent.change(screen.getByLabelText("Customer name"),{target:{value:"Kept customer"}});
    await screen.findByRole("option",{name:"Saudi Arabia"});
    fireEvent.change(screen.getByLabelText("Country"),{target:{value:"sa"}});
  }else fireEvent.change(screen.getByLabelText("Name in Arabic"),{target:{value:"Kept customer"}});
  fireEvent.change(screen.getByLabelText("Notes"),{target:{value:"Keep these notes"}});
  await waitFor(()=>expect((screen.getByRole("button",{name:"Add to City"}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button",{name:"Add to City"}));
  const dialog=await screen.findByRole("dialog",{name:"New list item"});
  expect((within(dialog).getByLabelText("Country") as HTMLSelectElement).value).toBe("sa");
  fireEvent.change(within(dialog).getByLabelText("Name (Arabic)"),{target:{value:"مدينة جديدة"}});
  fireEvent.change(within(dialog).getByLabelText("Name (English)"),{target:{value:"New city"}});
  fireEvent.click(within(dialog).getByRole("button",{name:"Save"}));
  await waitFor(()=>expect(screen.queryByRole("dialog")).toBeNull());
  expect((screen.getByLabelText("City") as HTMLSelectElement).value).toBe("new_city");
  expect(within(screen.getByLabelText("Other city selector")).getByRole("option",{name:"New city"})).toBeTruthy();
  expect((screen.getByLabelText("Notes") as HTMLTextAreaElement).value).toBe("Keep these notes");
  expect((screen.getByLabelText(form==="customer"?"Name in Arabic":"Customer name") as HTMLInputElement).value).toBe("Kept customer");
  expect(nav.push).not.toHaveBeenCalled();
});

async function addProduct(){
  await waitFor(()=>expect((screen.getByRole("button",{name:"+ Add a product"}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button",{name:"+ Add a product"}));
  const dialog=await screen.findByRole("dialog",{name:"New product"});
  fireEvent.change(within(dialog).getByLabelText("Name (Arabic)"),{target:{value:"منتج جديد"}});
  fireEvent.change(within(dialog).getByLabelText("Name (English)"),{target:{value:"New product"}});
  fireEvent.click(within(dialog).getByRole("button",{name:"Add property"}));
  const property=within(dialog).getByRole("group",{name:/New property/});
  fireEvent.change(within(property).getByLabelText("Name (Arabic)"),{target:{value:"العرض"}});
  fireEvent.change(within(property).getByLabelText("Name (English)"),{target:{value:"Inline width"}});
  fireEvent.change(within(property).getByLabelText("Key"),{target:{value:"inline_width"}});
  fireEvent.click(within(dialog).getByRole("button",{name:"Save"}));
  await waitFor(()=>expect(screen.queryByRole("dialog")).toBeNull());
}
it.each([false,true])("adds a product and immediately displays its template in a new quote (existing catalog: %s)",async(existing)=>{
  if(existing)products=[{id:"old",code:"PRD-OLD",key:"old_product",name_en:"Old product",name_ar:"قديم",kind:"finished",active:true,properties:[],default_unit:null,notes:null,actions:["edit"],created_at:"",updated_at:""}];
  ui(<QuoteForm/>);
  await waitFor(()=>expect((screen.getByRole("button",{name:"+ Add a product"}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText("Notes"),{target:{value:"Quote notes retained"}});
  await addProduct();
  expect((screen.getByLabelText("Product Type") as HTMLSelectElement).value).toBe("new_product");
  expect(await screen.findByLabelText("Inline width")).toBeTruthy();
  expect((screen.getByLabelText("Notes") as HTMLTextAreaElement).value).toBe("Quote notes retained");
  expect(nav.push).not.toHaveBeenCalled();
});

it("adds a product to a sales order and displays its template immediately",async()=>{
  ui(<CommercialOrderForm/>);
  // A manual order has editable lines rather than quotation snapshots.
  fireEvent.click(screen.getAllByRole("radio").find(input=>(input as HTMLInputElement).value==="direct")!);
  await addProduct();expect(await screen.findByLabelText("Inline width")).toBeTruthy();
  expect(nav.push).not.toHaveBeenCalled();
});

it("fixes the inline product kind and refreshes every product subscriber",async()=>{
  function Form(){const[value,set]=useState("");const all=useProducts();return <><ProductSelect kind="material" value={value} onChange={set} ariaLabel="Material"/><output aria-label="Observed products">{all?.map(p=>p.name_en).join(',')}</output></>;}
  ui(<Form/>);await waitFor(()=>expect((screen.getByRole("button",{name:"+ Add a product"}) as HTMLButtonElement).disabled).toBe(false));fireEvent.click(screen.getByRole("button",{name:"+ Add a product"}));
  const dialog=await screen.findByRole("dialog");expect((within(dialog).getByLabelText("Kind") as HTMLSelectElement).disabled).toBe(true);
  expect((within(dialog).getByLabelText("Kind") as HTMLSelectElement).value).toBe("material");
  fireEvent.change(within(dialog).getByLabelText("Name (Arabic)"),{target:{value:"مادة"}});fireEvent.change(within(dialog).getByLabelText("Name (English)"),{target:{value:"Material"}});
  fireEvent.click(within(dialog).getByRole("button",{name:"Save"}));
  await waitFor(()=>expect(screen.getByLabelText("Observed products").textContent).toBe("Material"));
  expect((screen.getByLabelText("Material") as HTMLSelectElement).value).toBe("material");
});

it("adds and selects a test parameter without discarding specification fields",async()=>{
  ui(<SpecificationForm/>);const title=await screen.findByLabelText("Title");fireEvent.change(title,{target:{value:"Keep specification title"}});
  fireEvent.click(screen.getByRole("button",{name:"+ Test parameter"}));const dialog=await screen.findByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Code"),{target:{value:"INLINE"}});
  fireEvent.change(within(dialog).getByLabelText("Arabic name"),{target:{value:"قياس"}});
  fireEvent.change(within(dialog).getByLabelText("English name"),{target:{value:"Inline parameter"}});
  fireEvent.click(within(dialog).getByRole("button",{name:"Save"}));
  expect(await screen.findByRole("group",{name:/Inline parameter/})).toBeTruthy();
  expect((title as HTMLInputElement).value).toBe("Keep specification title");expect(nav.push).not.toHaveBeenCalled();
});

it("hides inline creation from users without permission",async()=>{
  permission.allowed=false;ui(<><ProductSelect value="" onChange={()=>{}}/><ListSelect list="city" value="" onChange={()=>{}}/><SpecificationForm/></>);
  await screen.findByLabelText("Title");expect(screen.queryByRole("button",{name:"+ Add a product"})).toBeNull();expect(screen.queryByRole("button",{name:/Add to/})).toBeNull();expect(screen.queryByRole("button",{name:"+ Test parameter"})).toBeNull();
});

it("guards a keyboard-only customer selection in a shipment",async()=>{
  ui(<ShipmentForm/>);
  const customer=screen.getByRole("combobox",{name:"Customer"});
  fireEvent.focus(customer);await screen.findByRole("option",{name:/Customer.*C1/});
  fireEvent.keyDown(customer,{key:"ArrowDown"});fireEvent.keyDown(customer,{key:"Enter"});
  await waitFor(()=>expect((customer as HTMLInputElement).value).toContain("Customer"));
  const event=new Event("beforeunload",{cancelable:true});window.dispatchEvent(event);expect(event.defaultPrevented).toBe(true);
});

it("guards refresh, cancel and sidebar links, preserves data on stay, and stops warning after save",async()=>{
  function Form(){const[value,set]=useState("");const guard=useUnsavedFormChanges(value);return <><Link href="/dashboard">Sidebar</Link><form onChangeCapture={guard.onInteraction} onClickCapture={guard.onInteraction} onSubmit={e=>e.preventDefault()}>
    {guard.confirmation}<label>Draft<input value={value} onChange={e=>set(e.target.value)}/></label><Link href="/quotes">Cancel</Link><button type="button" onClick={guard.markSaved}>Save draft</button></form></>;}
  ui(<Form/>);fireEvent.change(screen.getByLabelText("Draft"),{target:{value:"Keep me"}});
  const unloading=new Event("beforeunload",{cancelable:true});window.dispatchEvent(unloading);expect(unloading.defaultPrevented).toBe(true);
  fireEvent.click(screen.getByRole("link",{name:"Cancel"}));expect(await screen.findByRole("alertdialog")).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Keep editing"}));expect((screen.getByLabelText("Draft") as HTMLInputElement).value).toBe("Keep me");
  fireEvent.click(screen.getByRole("link",{name:"Sidebar"}));fireEvent.click(await screen.findByRole("button",{name:"Discard and leave"}));expect(nav.push).toHaveBeenCalledWith("/dashboard");
  fireEvent.click(screen.getByRole("button",{name:"Save draft"}));
  const saved=new Event("beforeunload",{cancelable:true});window.dispatchEvent(saved);expect(saved.defaultPrevented).toBe(false);
  expect(screen.queryByRole("alertdialog")).toBeNull();
  fireEvent.change(screen.getByLabelText("Draft"),{target:{value:"Another edit"}});
  const editedAgain=new Event("beforeunload",{cancelable:true});window.dispatchEvent(editedAgain);expect(editedAgain.defaultPrevented).toBe(true);
});
