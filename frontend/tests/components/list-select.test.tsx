import {changeControl} from "./record-test-helpers";
import {cleanup,fireEvent,render,screen,within} from "@testing-library/react";
import {afterEach,beforeEach,expect,it,vi} from "vitest";
import {NextIntlClientProvider} from "next-intl";
import {ListSelect} from "@/features/masterdata/components/ListSelect";
import masterdata from "@/i18n/locales/ar/masterdata.json";
import common from "@/i18n/locales/ar/common.json";
import directory from "@/i18n/locales/ar/directory.json";

const state=vi.hoisted(()=>({canManage:true,items:[] as unknown[]}));
vi.mock("@/features/auth/permission-hooks",()=>({usePermission:()=>state.canManage}));
vi.mock("@/features/masterdata/catalog",()=>({useListItems:()=>state.items,refreshCatalog:vi.fn()}));
afterEach(cleanup);
beforeEach(()=>{state.canManage=true;state.items=[{key:"sa",name_ar:"السعودية",name_en:"Saudi Arabia",active:true}];});
const ui=(onChange=vi.fn())=>render(<NextIntlClientProvider locale="ar" timeZone="UTC" messages={{masterdata,common,directory}}>
  <ListSelect list="country" value="" ariaLabel="الدولة" onChange={onChange}/>
</NextIntlClientProvider>);

it("places an accessible add button beside the select and keeps management inside its dialog",async()=>{
  const onChange=vi.fn();ui(onChange);
  const select=screen.getByRole("combobox"),add=screen.getByRole("button",{name:"إضافة إلى الدولة"});
  expect(add.closest("label")).toBe(select.closest("label"));expect(add.compareDocumentPosition(select)&Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
  expect(add.className).toContain("manage");expect(screen.queryByRole("link")).toBeNull();
  changeControl(select,{target:{value:"sa"}});expect(onChange).toHaveBeenCalledWith("sa",state.items[0]);
  fireEvent.click(add);const dialog=await screen.findByRole("dialog");
  const manage=within(dialog).getByRole("link",{name:masterdata.select.manageInNewTab});
  expect(manage.getAttribute("href")).toBe("/master-data/lists?list=country");expect(manage.getAttribute("target")).toBe("_blank");
});
it("hides the add action without permission",()=>{state.canManage=false;ui();expect(screen.queryByRole("button")).toBeNull();expect(screen.getByRole("combobox")).toBeTruthy();});
it("keeps free text and offers inline creation when the list is empty",()=>{state.items=[];ui();expect(screen.getByRole("textbox")).toBeTruthy();expect(screen.getByRole("button",{name:"إضافة إلى الدولة"})).toBeTruthy();expect(screen.queryByRole("link")).toBeNull();});
