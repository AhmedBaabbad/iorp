import {act,cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {NextIntlClientProvider} from "next-intl";
import {afterEach,beforeEach,expect,it,vi} from "vitest";
import {useListPage} from "@/hooks/useListPage";
import {useClientListPage} from "@/hooks/useClientListPage";
import {Pagination,ListToolbar} from "@/components/pagination";
import {readPage} from "@/lib/page-response";
import common from "@/i18n/locales/en/common.json";
import {listRouter} from "./list-navigation";
vi.mock("next/navigation",async()=> (await import("./list-navigation")).listNavigation);
afterEach(cleanup);
beforeEach(()=>{window.history.replaceState(null,"","/records?page=2");});
type Row={id:string};
let controller:ReturnType<typeof useListPage<Row>>;
function Harness(){
  const page=useListPage<Row>({search:"",status:""});controller=page;
  return <><ListToolbar search={page.filters.search} searchHint="Find records" onSearch={value=>page.set("search",value)} onClear={page.clear}/><Pagination {...page.pagination}/></>;
}
function ui(node:React.ReactNode){return render(<NextIntlClientProvider locale="en" messages={{common}}>{node}</NextIntlClientProvider>);}
it("keeps page and page size in the URL and resets the page when searching",async()=>{
  ui(<Harness/>);
  act(()=>controller.accept({items:[{id:"51"}],total:120,page:2,page_size:50,pages:3},()=>{}));
  expect(screen.getByText("Showing 51 to 100 of 120")).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Page 3"}));
  await waitFor(()=>expect(controller.params.page).toBe("3"));
  fireEvent.change(screen.getByRole("combobox"),{target:{value:"25"}});
  await waitFor(()=>expect(controller.params).toMatchObject({page:"1",page_size:"25"}));
  act(()=>listRouter.replace("/records?page=2&page_size=25"));
  fireEvent.change(screen.getByPlaceholderText("Find records"),{target:{value:"gulf"}});
  await waitFor(()=>expect(controller.params).toMatchObject({page:"1",page_size:"25",search:"gulf"}));
});
it("rejects a late response for an older filter and clamps an empty deleted page",async()=>{
  ui(<Harness/>);const stale=controller.accept;const write=vi.fn();
  act(()=>listRouter.replace("/records?page=2&search=new"));
  act(()=>stale({items:[{id:"stale"}],total:120,page:2,page_size:50,pages:3},write));
  expect(write).not.toHaveBeenCalled();
  act(()=>controller.accept({items:[],total:1,page:2,page_size:50,pages:1},write));
  await waitFor(()=>expect(controller.params.page).toBe("1"));
  expect(window.location.search).toBe("?search=new");
});
it("slices a legacy array response without changing the original array",()=>{
  const rows=Array.from({length:65},(_,id)=>({id:String(id)}));
  expect(readPage(rows,2,50)).toMatchObject({items:rows.slice(50),total:65,pages:2,page_size:50,page:2});
  expect(rows).toHaveLength(65);
});
it("does not clamp a small catalog before its request has finished",async()=>{
  function Catalog({ready}:{ready:boolean}){const page=useClientListPage([{id:"1"}],row=>row.id,ready);return <Pagination {...page.pagination}/>;}
  const view=ui(<Catalog ready={false}/>);expect(window.location.search).toBe("?page=2");
  view.rerender(<NextIntlClientProvider locale="en" messages={{common}}><Catalog ready/></NextIntlClientProvider>);
  await waitFor(()=>expect(window.location.search).toBe(""));
});
