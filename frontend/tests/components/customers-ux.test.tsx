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
function Customer({canAssignOwner=true}:{canAssignOwner?:boolean}) {
  const [values,setValues]=useState(defaultCustomerFormValues);
  return <form><CustomerFields values={values} onChange={patch=>setValues(old=>({...old,...patch}))} disabled={false} canAssignOwner={canAssignOwner}
    eligibleOwners={[]} loadingOwners={false} ownerName="Owner"/></form>;
}
it.each([true,false])("keeps the original single grid, field order and full-width notes (assign owner: %s)", canAssignOwner => {
  const {container}=ui(<Customer canAssignOwner={canAssignOwner}/>);
  expect(container.querySelector("legend, fieldset, h1, h2, h3, h4, h5, h6")).toBeNull();
  const form=container.querySelector("form")!;
  const grid=form.firstElementChild as HTMLElement;
  expect(grid.style.display).toBe("grid"); expect(grid.style.gap).toBe("18px");
  expect(grid.style.gridTemplateColumns).toBe("repeat(auto-fit, minmax(220px, 1fr))");
  const labels=()=>Array.from(grid.children).map(label=>label.firstElementChild?.textContent?.replace(/\s*\*$/,"").trim());
  const fields=(messages.commercial as {customers:{fields:Record<string,string>}}).customers.fields;
  expect(labels()).toEqual([fields.name,fields.sector,"Country","City",fields.status,fields.relationshipStage,
    fields.priority,fields.opportunitySource,fields.salesOwner,fields.keyInfluencerName]);
  fireEvent.change(screen.getByRole("combobox",{name:"City"}),{target:{value:"sa_other"}});
  expect(labels().slice(0,5)).toEqual([fields.name,fields.sector,"Country","City","City name"]);
  expect((screen.getByRole("textbox",{name:"City name"}) as HTMLInputElement).required).toBe(true);
  expect(form.children[1].tagName).toBe("P");
  expect(form.children[2].querySelector("textarea")).toBe(screen.getByRole("textbox",{name:fields.notes}));
  expect((screen.getByRole("textbox",{name:fields.notes}) as HTMLTextAreaElement).style.minHeight).toBe("110px");
  expect(screen.queryByRole("textbox",{name:"Contact name"})).toBeNull();
  expect(screen.queryByRole("textbox",{name:"Mobile"})).toBeNull();
});
it("never sends inline contacts or legacy customer phone/email", () => {
  expect(defaultCustomerFormValues.country).toBe("sa");
  const body=toCustomerCreateRequest({...defaultCustomerFormValues,name:" Client "},false);
  expect(body.name).toBe("Client");
  expect(body).not.toHaveProperty("phone"); expect(body).not.toHaveProperty("email");
  expect(toCustomerCreateRequest(defaultCustomerFormValues,false)).not.toHaveProperty("primary_contact");
  expect(body).not.toHaveProperty("primary_contact");
  expect(Object.keys(defaultCustomerFormValues).some(key=>key.startsWith("contact_"))).toBe(false);
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
