import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, expect, it, vi } from "vitest";
import { DirectoryPanel } from "@/features/reference-directory/DirectoryPanel";
import { ApiClientError } from "@/lib/api-client";
import en from "@/i18n/locales/en/directory.json";
import ar from "@/i18n/locales/ar/directory.json";

const mocks=vi.hoisted(()=>({api:vi.fn()}));
vi.mock("@/lib/api-client",async original=>({...await original<object>(),apiClient:mocks.api}));
vi.mock("@/features/auth/permission-hooks",()=>({usePermission:()=>true}));
vi.mock("@/features/masterdata",()=>({ListSelect:()=>null,useListName:()=>(key:string)=>key}));
afterEach(cleanup);

it("keeps every directory error translated in both languages",()=>{
  expect(Object.keys(ar.errors).sort()).toEqual(Object.keys(en.errors).sort());
  expect(Object.keys(en.errors)).toHaveLength(12);
  for(const value of [...Object.values(ar.errors),...Object.values(en.errors)])expect(value.trim()).not.toBe("");
});

it.each(Object.entries(en.errors))("renders the specific %s message",async(code,message)=>{
  mocks.api.mockImplementation((_path:string,options?:{method?:string})=>options?.method
    ?Promise.reject(new ApiClientError("failed",code==="DIRECTORY_CHANGED"?409:422,{detail:code}))
    :Promise.resolve([]));
  render(<NextIntlClientProvider locale="en" messages={{directory:en,messages:{}}}>
    <DirectoryPanel path="/shipping/directory/carriers" kind="carriers" writePermission="shipping:directory:write"/>
  </NextIntlClientProvider>);
  fireEvent.click(screen.getByRole("button",{name:"Add"}));
  fireEvent.change(screen.getByLabelText("Name"),{target:{value:"Carrier"}});
  fireEvent.click(screen.getByRole("button",{name:"Save"}));
  expect((await screen.findByRole("alert")).textContent).toContain(message);
  if(code==="DIRECTORY_CHANGED"){
    fireEvent.click(screen.getByRole("button",{name:"Reload"}));
    expect(await screen.findByRole("button",{name:"Add"})).toBeTruthy();
  }
});

it("reloads a conflicted record before retrying with its current version",async()=>{
  let changed=false;
  const writes: {version:number}[]=[];
  mocks.api.mockImplementation((_path:string,options?:{method?:string;body:{version:number}})=>{
    if(options?.method){
      writes.push(options.body);
      if(!changed){changed=true;return Promise.reject(new ApiClientError("conflict",409,{detail:"DIRECTORY_CHANGED"}));}
      return Promise.resolve({});
    }
    return Promise.resolve([{id:"c1",name:changed?"Remote name":"Original name",active:true,version:changed?2:1}]);
  });
  render(<NextIntlClientProvider locale="en" messages={{directory:en,messages:{}}}>
    <DirectoryPanel path="/shipping/directory/carriers" kind="carriers" writePermission="shipping:directory:write"/>
  </NextIntlClientProvider>);
  fireEvent.click(await screen.findByRole("button",{name:"Edit"}));
  fireEvent.click(screen.getByRole("button",{name:"Save"}));
  fireEvent.click(await screen.findByRole("button",{name:"Reload"}));
  await waitFor(()=>expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Remote name"));
  fireEvent.click(screen.getByRole("button",{name:"Save"}));
  await waitFor(()=>expect(writes.map(row=>row.version)).toEqual([1,2]));
});
