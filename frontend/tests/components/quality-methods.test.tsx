import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {NextIntlClientProvider,useTranslations} from "next-intl";
import {useState,type ReactNode} from "react";
import {afterEach,beforeAll,beforeEach,expect,it,vi} from "vitest";
import {loadMessages} from "@/i18n/messages";
import {TestMethodSelect} from "@/features/quality-specifications/components/TestMethodSelect";
import {ParameterCreateDialog} from "@/features/quality-specifications/components/ParameterFormFields";
import {qualityErrorMessage} from "@/features/quality-checks/components/quality-errors";
import {ApiClientError} from "@/lib/api-client";
import quality from "@/i18n/locales/en/quality.json";
import qualityAr from "@/i18n/locales/ar/quality.json";

const api=vi.hoisted(()=>({apiClient:vi.fn()}));
vi.mock("@/lib/api-client",async original=>({...await original<object>(),apiClient:api.apiClient}));
let messages:Record<string,Awaited<ReturnType<typeof loadMessages>>>;
beforeAll(async()=>{messages={en:await loadMessages("en"),ar:await loadMessages("ar")};});
beforeEach(()=>api.apiClient.mockReset());afterEach(cleanup);
const ui=(node:ReactNode,locale="en")=>render(<NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">{node}</NextIntlClientProvider>);
const item={id:"official",list:"test_method",key:"micrometer",name_ar:"ميكرومتر",name_en:"Micrometer",active:true,parent_key:null,sort_order:1};
function Harness({initial={method_ar:"",method_en:""}}:{initial?:{method_ar:string;method_en:string}}){
  const [method,set]=useState(initial);
  return <><TestMethodSelect {...method} onChange={set} label="Method" labelAr="Arabic method" labelEn="English method"/><output aria-label="Stored method">{JSON.stringify(method)}</output></>;
}
it.each(["en","ar"])("selects one official method and stores both names in %s",async locale=>{
  api.apiClient.mockResolvedValue([item]);ui(<Harness/>,locale);
  const input=screen.getByRole("combobox",{name:"Method"});
  await waitFor(()=>expect((input as HTMLInputElement).disabled).toBe(false));
  expect(screen.queryByLabelText("Arabic method")).toBeNull();
  fireEvent.focus(input);fireEvent.click(screen.getByRole("option",{name:locale==="ar"?item.name_ar:item.name_en}));
  expect(screen.getByLabelText("Stored method").textContent).toBe(JSON.stringify({method_en:item.name_en,method_ar:item.name_ar}));
  expect((input as HTMLInputElement).value).toBe(locale==="ar"?item.name_ar:item.name_en);
});
it("only shows bilingual free text for an empty official list",async()=>{
  api.apiClient.mockResolvedValue([]);ui(<Harness/>);
  fireEvent.change(await screen.findByLabelText("Arabic method"),{target:{value:"طريقة حرة"}});
  fireEvent.change(screen.getByLabelText("English method"),{target:{value:"Free method"}});
  expect(screen.getByLabelText("Stored method").textContent).toContain('"method_en":"Free method"');
  expect(screen.queryByRole("combobox")).toBeNull();
});
it("preserves a legacy pair without adding editable text fields",async()=>{
  api.apiClient.mockResolvedValue([item]);ui(<Harness initial={{method_ar:"قديم",method_en:"Legacy"}}/>,"ar");
  await waitFor(()=>expect((screen.getByRole("combobox",{name:"Method"}) as HTMLInputElement).value).toBe("قديم"));
  expect(screen.getByLabelText("Stored method").textContent).toBe(JSON.stringify({method_ar:"قديم",method_en:"Legacy"}));
  expect(screen.queryByLabelText("Arabic method")).toBeNull();
});
it("never treats a failed list request as an unconfigured list",async()=>{
  api.apiClient.mockRejectedValueOnce(new Error("Offline")).mockResolvedValue([]);ui(<Harness/>);
  await screen.findByRole("alert");expect(screen.queryByLabelText("English method")).toBeNull();
  fireEvent.click(screen.getByRole("button",{name:quality.methods.retry}));
  expect(await screen.findByLabelText("English method")).toBeTruthy();
});
it("sends the two official names when creating a parameter",async()=>{
  api.apiClient.mockImplementation((_path:string,options?:{method?:string})=>Promise.resolve(options?.method==="POST"?{id:"created"}:[item]));
  ui(<ParameterCreateDialog onCreated={vi.fn()} onClose={vi.fn()}/>);
  fireEvent.change(screen.getByLabelText(quality.parameters.fields.code),{target:{value:"METHOD"}});
  fireEvent.change(screen.getByLabelText(quality.parameters.fields.nameAr),{target:{value:"قياس"}});
  fireEvent.change(screen.getByLabelText(quality.parameters.fields.nameEn),{target:{value:"Measurement"}});
  const input=screen.getByRole("combobox",{name:quality.parameters.fields.method});
  await waitFor(()=>expect((input as HTMLInputElement).disabled).toBe(false));
  fireEvent.focus(input);fireEvent.click(screen.getByRole("option",{name:item.name_en}));
  fireEvent.submit(screen.getByRole("dialog"));
  await waitFor(()=>expect(api.apiClient.mock.calls.find(([,options])=>options?.method==="POST")?.[1]?.body).toMatchObject({method_ar:item.name_ar,method_en:item.name_en}));
});
it("translates an unavailable official value",()=>{
  function Failure(){const t=useTranslations("quality.errors");return <p>{qualityErrorMessage(new ApiClientError("Unavailable",422,{detail:{code:"REFERENCE_VALUE_UNAVAILABLE"}}),t)}</p>;}
  ui(<Failure/>,"ar");expect(screen.getByText(qualityAr.errors.REFERENCE_VALUE_UNAVAILABLE)).toBeTruthy();
});
