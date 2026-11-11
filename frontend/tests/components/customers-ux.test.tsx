import { useState, type ReactNode } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeAll, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import { CountryCityFields } from "@/components/forms/CountryCityFields";
import { MapLink, mapHref } from "@/components/MapLink";
import { CustomerFields } from "@/features/customers/CustomerFields";
import { defaultCustomerFormValues, toCustomerCreateRequest } from "@/features/customers/customer-form";

vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: () => true }));
vi.mock("@/features/masterdata/catalog", () => ({ useListItems: (list: string) => ({
  country: [{key:"sa",name_en:"Saudi Arabia"},{key:"ae",name_en:"United Arab Emirates"}],
  city: [{key:"riyadh",name_en:"Riyadh",parent_key:"sa"},{key:"sa_other",name_en:"Other",parent_key:"sa"},
    {key:"ae_dubai",name_en:"Dubai",parent_key:"ae"},{key:"ae_other",name_en:"Other",parent_key:"ae"}],
}[list] ?? []).map(row => ({...row,active:true,name_ar:row.name_en})) }));
let messages: Record<string, unknown>;
beforeAll(async () => { messages = await loadMessages("en") as Record<string, unknown>; });
afterEach(cleanup);
const ui = (children: ReactNode) => render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">{children}</NextIntlClientProvider>);

function Location({country=""}:{country?:string}) {
  const [value,setValue]=useState({country,city:"",city_other:""});
  return <CountryCityFields value={value} onChange={patch=>setValue(old=>({...old,...patch}))}/>;
}
it("orders country before city, disables city until selected and filters cities", () => {
  ui(<Location/>);
  const country=screen.getByRole("combobox",{name:"Country"});
  const city=screen.getByRole("combobox",{name:"City"}) as HTMLSelectElement;
  expect(screen.getAllByRole("combobox")).toEqual([country,city]);
  expect(city.disabled).toBe(true);
  fireEvent.change(country,{target:{value:"ae"}});
  expect(city.disabled).toBe(false);
  expect(screen.queryByRole("option",{name:"Riyadh"})).toBeNull();
  expect(screen.getByRole("option",{name:"Dubai"})).toBeTruthy();
});
it("requires Other city name and clears both fields when the country changes", () => {
  ui(<Location country="sa"/>);
  const city=screen.getByRole("combobox",{name:"City"}) as HTMLSelectElement;
  fireEvent.change(city,{target:{value:"sa_other"}});
  const other=screen.getByRole("textbox",{name:"City name"}) as HTMLInputElement;
  expect(other.required).toBe(true);
  fireEvent.change(other,{target:{value:"Synthetic city"}});
  fireEvent.change(screen.getByRole("combobox",{name:"Country"}),{target:{value:"ae"}});
  expect(city.value).toBe("");
  expect(screen.queryByRole("textbox",{name:"City name"})).toBeNull();
  fireEvent.change(city,{target:{value:"ae_other"}});
  expect((screen.getByRole("textbox",{name:"City name"}) as HTMLInputElement).value).toBe("");
});
function Customer({creating=true}:{creating?:boolean}) {
  const [values,setValues]=useState(defaultCustomerFormValues);
  return <CustomerFields values={values} onChange={patch=>setValues(old=>({...old,...patch}))} disabled={false} canAssignOwner={false}
    eligibleOwners={[]} loadingOwners={false} creating={creating} ownerName="Owner"/>;
}
it("offers optional primary contact only on creation; any field makes its name required", () => {
  const view=ui(<Customer/>);
  const name=screen.getByRole("textbox",{name:"Contact name"}) as HTMLInputElement;
  expect(name.required).toBe(false);
  fireEvent.change(screen.getByRole("textbox",{name:"Mobile"}),{target:{value:"5551234"}});
  expect(name.required).toBe(true);
  view.unmount(); ui(<Customer creating={false}/>);
  expect(screen.queryByRole("textbox",{name:"Contact name"})).toBeNull();
});
it("sends one nested contact and never writes legacy customer phone/email", () => {
  expect(defaultCustomerFormValues.country).toBe("sa");
  const body=toCustomerCreateRequest({...defaultCustomerFormValues,name:" Client ",contact_name:" Buyer ",contact_phone:"555"},false);
  expect(body.primary_contact).toEqual({name:"Buyer",phone:"555",email:undefined,role:undefined});
  expect(body).not.toHaveProperty("phone"); expect(body).not.toHaveProperty("email");
  expect(toCustomerCreateRequest(defaultCustomerFormValues,false)).not.toHaveProperty("primary_contact");
  expect(toCustomerCreateRequest({...defaultCustomerFormValues,contact_name:"Ignored on edit"},false,false)).not.toHaveProperty("primary_contact");
});
it("uses HTTPS explicit links or encoded address search and isolates the opened page", () => {
  expect(mapHref("https://maps.example.test/a","Ignored")).toBe("https://maps.example.test/a");
  expect(mapHref("javascript:alert(1)","Road & 1","New city","Saudi Arabia"))
    .toBe("https://www.google.com/maps/search/?api=1&query=Road%20%26%201%2C%20New%20city%2C%20Saudi%20Arabia");
  ui(<MapLink locationUrl="https://maps.example.test/a"/>);
  const link=screen.getByRole("link",{name:"Open in Google Maps"});
  expect(link.getAttribute("target")).toBe("_blank"); expect(link.getAttribute("rel")).toBe("noopener noreferrer");
});
it.each([null,"javascript:alert(1)","http://unsafe.test","data:text/html,unsafe"])("hides missing addresses and unsafe legacy URLs (%s)",url=>{
  ui(<MapLink locationUrl={url}/>); expect(screen.queryByRole("link")).toBeNull();
});
