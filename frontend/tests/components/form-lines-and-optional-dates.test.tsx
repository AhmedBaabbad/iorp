import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {NextIntlClientProvider} from "next-intl";
import {useState} from "react";
import {afterEach,beforeAll,expect,it,vi} from "vitest";
import {loadMessages} from "@/i18n/messages";
import {OptionalDateInput} from "@/components/forms/OptionalDateInput";
import {useRevealNewRow} from "@/hooks/useRevealNewRow";
type Messages=Awaited<ReturnType<typeof loadMessages>>;
let ar:Messages;
beforeAll(async()=>{ar=await loadMessages("ar");});
afterEach(cleanup);
const ui=(node:React.ReactNode)=>render(<NextIntlClientProvider locale="ar" messages={ar} timeZone="UTC">{node}</NextIntlClientProvider>);

function DateHarness({initial,onValue}:{initial:string;onValue:(v:string)=>void}){
  const [value,setValue]=useState(initial);
  return <OptionalDateInput label="تاريخ التسليم" value={value} onChange={v=>{setValue(v);onValue(v);}}/>;
}

it("keeps an optional date empty until it is asked for, and clears it when the tick is removed",()=>{
  const onValue=vi.fn();
  ui(<DateHarness initial="" onValue={onValue}/>);
  expect(screen.getByText("بدون تاريخ")).toBeTruthy();
  expect(screen.queryByLabelText("تاريخ التسليم")).toBeNull();
  fireEvent.click(screen.getByRole("checkbox",{name:"تحديد تاريخ: تاريخ التسليم"}));
  fireEvent.change(screen.getByLabelText("تاريخ التسليم"),{target:{value:"2026-12-10"}});
  expect(onValue).toHaveBeenLastCalledWith("2026-12-10");
  fireEvent.click(screen.getByRole("checkbox",{name:"تحديد تاريخ: تاريخ التسليم"}));
  expect(onValue).toHaveBeenLastCalledWith("");
  expect(screen.getByText("بدون تاريخ")).toBeTruthy();
});

it("shows a saved date ticked and editable",()=>{
  ui(<DateHarness initial="2026-12-01" onValue={vi.fn()}/>);
  expect((screen.getByRole("checkbox") as HTMLInputElement).checked).toBe(true);
  expect((screen.getByLabelText("تاريخ التسليم") as HTMLInputElement).value).toBe("2026-12-01");
});

function Lines({initial=1}:{initial?:number}){
  const [lines,setLines]=useState(Array.from({length:initial},(_,i)=>i));
  const reveal=useRevealNewRow(lines.length,"test-lines");
  return <>
    {lines.map(n=><div key={n} data-row="test-lines"><input aria-label={`line ${n+1}`}/></div>)}
    <button type="button" onClick={()=>{reveal();setLines(old=>[...old,old.length]);}}>add</button>
    <button type="button" onClick={()=>setLines(old=>[...old,old.length,old.length+1])}>load</button>
  </>;
}

it("moves to a line the user adds and focuses it, but not to lines loaded from the server",()=>{
  const scroll=vi.fn();
  Element.prototype.scrollIntoView=scroll;
  ui(<Lines/>);
  fireEvent.click(screen.getByText("load"));
  expect(scroll).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("add"));
  expect(screen.getAllByRole("textbox")).toHaveLength(4);
  expect(scroll).toHaveBeenCalledTimes(1);
  expect(document.activeElement).toBe(screen.getByLabelText("line 4"));
  // The add button stays under the last line.
  const add=screen.getByText("add");
  expect(screen.getByLabelText("line 4").compareDocumentPosition(add)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
