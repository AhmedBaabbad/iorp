import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {NextIntlClientProvider,createTranslator} from "next-intl";
import {useState} from "react";
import {afterEach,beforeEach,expect,it,vi} from "vitest";
import {CustomerPicker} from "@/features/customers/customer-picker";
import {ProductionOrderPicker} from "@/features/production-orders/components/ProductionOrderPicker";
import {RecordCombobox} from "@/components/ui/RecordCombobox";
import directory from "@/i18n/locales/en/directory.json";
import commercial from "@/i18n/locales/en/commercial.json";
import production from "@/i18n/locales/en/production.json";
import englishErrors from "@/i18n/locales/en/messages.json";
import arabicErrors from "@/i18n/locales/ar/messages.json";
import {getApiErrorMessage} from "@/lib/api-error-handler";
import {ApiClientError} from "@/lib/api-client";
const api=vi.hoisted(()=>({customers:vi.fn(),byIds:vi.fn(),orders:vi.fn()}));
vi.mock("@/features/customers/customer-api",()=>({lookupCustomers:api.customers,customersByIds:api.byIds}));
vi.mock("@/features/production-orders/api/production-orders-api",()=>({lookupProductionOrders:api.orders}));
const customer={id:"c1",name:"Gulf Packaging",name_en:"Gulf Packaging",name_ar:"مصنع الخليج",customer_code:"C-1"};
const order={id:"o1",production_order_number:"PO-2026-001",product_type:"Film"};
const ui=(node:React.ReactNode)=>render(<NextIntlClientProvider locale="en" messages={{directory,commercial,production}}>{node}</NextIntlClientProvider>);
beforeEach(()=>{vi.clearAllMocks();api.customers.mockResolvedValue([customer]);api.byIds.mockResolvedValue([customer]);api.orders.mockImplementation(({ids}:{ids?:string[]})=>Promise.resolve(ids?[order]:[order]));});
afterEach(cleanup);

it("searches customers in the same input after 250ms, selects and preserves the selected record",async()=>{
  const changed=vi.fn();
  function Form(){const[value,set]=useState("");return <CustomerPicker value={value} ariaLabel="Customer" onChange={(id,row)=>{set(id);changed(id,row);}}/>;}
  ui(<Form/>);
  const input=screen.getByRole("combobox",{name:"Customer"});
  fireEvent.focus(input);fireEvent.change(input,{target:{value:"Gul"}});
  expect(api.customers).not.toHaveBeenCalled();
  await waitFor(()=>expect(api.customers).toHaveBeenCalledWith("Gul"));
  fireEvent.click(await screen.findByRole("option",{name:/Gulf Packaging/}));
  expect(changed).toHaveBeenCalledWith("c1",customer);
  expect((input as HTMLInputElement).value).toBe("Gulf Packaging");
  expect(document.querySelector('input[type="search"],select')).toBeNull();
});

it("hydrates the selected customer by id when editing even if absent from search results",async()=>{
  api.customers.mockResolvedValue([]);
  ui(<CustomerPicker value="c1" ariaLabel="Customer" onChange={()=>{}}/>);
  await waitFor(()=>expect((screen.getByRole("combobox") as HTMLInputElement).value).toBe("Gulf Packaging"));
  expect(api.byIds).toHaveBeenCalledWith(["c1"]);
});

it("searches production orders with status constraints and hydrates a saved order",async()=>{
  const {unmount}=ui(<ProductionOrderPicker value="o1" statuses={["released"]} ariaLabel="Order" onChange={()=>{}}/>);
  await waitFor(()=>expect((screen.getByRole("combobox") as HTMLInputElement).value).toBe(order.production_order_number));
  expect(api.orders).toHaveBeenCalledWith({ids:["o1"]});
  fireEvent.change(screen.getByRole("combobox"),{target:{value:"2026"}});
  await waitFor(()=>expect(api.orders).toHaveBeenCalledWith({search:"2026",statuses:["released"]}));
  unmount();
});

it("clearing a record filter means all and submits identifiers rather than display names",()=>{
  const changed=vi.fn();
  function Filter(){const[value,set]=useState("c1");return <form aria-label="Filters"><RecordCombobox aria-label="Customer" name="customer_id" value={value} onChange={id=>{set(id);changed(id);}}><option value="">All</option><option value="c1">Gulf Packaging</option></RecordCombobox></form>;}
  ui(<Filter/>);
  expect(new FormData(screen.getByRole("form") as HTMLFormElement).get("customer_id")).toBe("c1");
  fireEvent.click(screen.getByRole("button",{name:"Clear Customer"}));
  expect(changed).toHaveBeenCalledWith("");
  expect((screen.getByRole("combobox") as HTMLInputElement).placeholder).toBe("All");
  expect(new FormData(screen.getByRole("form") as HTMLFormElement).get("customer_id")).toBe("");
});

it.each(["en","ar"])("translates the unit error for schema and saved-row validation in %s",locale=>{
  const messages=locale==="ar"?arabicErrors:englishErrors;
  const t=createTranslator({locale,messages});
  for(const detail of ["UNIT_UNKNOWN",{code:"UNIT_UNKNOWN"},[{type:"UNIT_UNKNOWN",loc:["body","unit"],msg:"UNIT_UNKNOWN"}]]){
    expect(getApiErrorMessage(new ApiClientError("invalid",422,{detail}),key=>t(key as Parameters<typeof t>[0])))
      .toBe(messages.validation.unitUnknown);
  }
});

it("keeps group context searchable when record labels would otherwise be identical",()=>{
  const selected=vi.fn();
  ui(<RecordCombobox aria-label="Permission" value="" onChange={selected}>
    <optgroup label="Commercial"><option value="commercial-read">Read</option></optgroup>
    <optgroup label="Shipping"><option value="shipping-read">Read</option></optgroup>
  </RecordCombobox>);
  fireEvent.change(screen.getByRole("combobox"),{target:{value:"Shipping"}});
  expect(screen.getAllByRole("option")).toHaveLength(1);
  fireEvent.click(screen.getByRole("option",{name:/Read.*Shipping/}));
  expect(selected).toHaveBeenCalledWith("shipping-read");
});
