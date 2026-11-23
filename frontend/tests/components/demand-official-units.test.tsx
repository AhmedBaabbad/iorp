import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {NextIntlClientProvider} from "next-intl";
import {afterEach,beforeAll,expect,it,vi} from "vitest";
import {loadMessages} from "@/i18n/messages";
import {DemandForm} from "@/features/production-demands/form";
import {UNITS} from "@/lib/units";
vi.mock("next/navigation",()=>({useRouter:()=>({push:vi.fn()})}));
vi.mock("@/features/auth/permission-hooks",()=>({usePermission:()=>true}));
vi.mock("@/components/layout/page-frame",()=>({PageFrame:({children}:{children:React.ReactNode})=><main>{children}</main>}));
vi.mock("@/features/production-demands/api",()=>({demandsApi:{customers:()=>Promise.resolve([])}}));
vi.mock("@/features/masterdata",()=>({useProducts:()=>[],useProductName:()=>String,
  ProductSelect:({onChange}:{onChange:(key:string,product:{default_unit:string})=>void})=><button type="button" aria-label="Choose film" onClick={()=>onChange("film",{default_unit:"kg"})}>Choose film</button>}));
let messages:Awaited<ReturnType<typeof loadMessages>>;
beforeAll(async()=>{messages=await loadMessages("en");});
afterEach(cleanup);
it("offers only official units on a new demand and applies the product default",()=>{
  const {container}=render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC"><DemandForm/></NextIntlClientProvider>);
  fireEvent.click(screen.getByRole("button",{name:"Add Item"}));
  const unit=screen.getByRole("combobox",{name:"Unit"}) as HTMLSelectElement;
  expect(unit.tagName).toBe("SELECT");
  expect(Array.from(unit.options).map(option=>option.value).filter(Boolean).sort()).toEqual([...UNITS].sort());
  expect(container.querySelector('datalist,input[list="demand-units"]')).toBeNull();
  fireEvent.click(screen.getByRole("button",{name:"Choose film"}));
  expect(unit.value).toBe("kg");
});
