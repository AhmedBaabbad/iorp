import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { Tabs } from "@/components/ui/Tabs";
import { RecordDialog } from "@/components/ui/RecordDialog";
import { Combobox } from "@/components/ui/Combobox";
import en from "@/i18n/locales/en/directory.json";
import ar from "@/i18n/locales/ar/directory.json";
import common from "@/i18n/locales/en/common.json";
const ui=(node:React.ReactNode,locale="en")=>render(<NextIntlClientProvider locale={locale} messages={{directory:locale==="ar"?ar:en,common}}>{node}</NextIntlClientProvider>);
afterEach(()=>{cleanup();window.history.replaceState(null,"","/");});

it.each(["en","ar"])("navigates accessible tabs with keyboard and keeps the URL in %s",locale=>{
  window.history.replaceState(null,"","/?page=2&tab=second");
  ui(<Tabs label="Sections" items={[{id:"first",label:"First",content:<p>First panel</p>},{id:"second",label:"Second",content:<p>Second panel</p>}]}/>,locale);
  const second=screen.getByRole("tab",{name:"Second"});
  expect(second.getAttribute("aria-selected")).toBe("true");
  fireEvent.keyDown(second,{key:locale==="ar"?"ArrowRight":"ArrowLeft"});
  expect(document.activeElement).toBe(screen.getByRole("tab",{name:"First"}));
  expect(window.location.search).toBe("?page=2&tab=first");
  expect(screen.getByRole("tabpanel").textContent).toBe("First panel");
  fireEvent.keyDown(document.activeElement!,{key:"End"});
  expect(screen.getByRole("tabpanel").textContent).toBe("Second panel");
  fireEvent.keyDown(document.activeElement!,{key:"Home"});
  expect(screen.getByRole("tabpanel").textContent).toBe("First panel");
});

it("keeps a failed record save open with its field values, then closes after success",async()=>{
  const save=vi.fn().mockRejectedValueOnce(new Error("failed")).mockResolvedValueOnce(true),close=vi.fn();
  ui(<RecordDialog title="Edit record" onSave={save} onClose={close}><label>Name<input defaultValue="Kept name"/></label></RecordDialog>);
  fireEvent.click(screen.getByRole("button",{name:"Save"}));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(close).not.toHaveBeenCalled();
  expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Kept name");
  fireEvent.click(screen.getByRole("button",{name:"Save"}));
  await waitFor(()=>expect(close).toHaveBeenCalledOnce());
});

it("searches, shows secondary option details, selects and clears a combobox",()=>{
  function Form(){const[value,set]=useState("");return <Combobox label="Contact" value={value} onChange={set}
    options={[{id:"a",name:"Ali",detail:"Manager · +966551234567"},{id:"b",name:"Sara",detail:"Purchasing"}]}/>;}
  ui(<Form/>);
  const input=screen.getByRole("combobox",{name:"Contact"});
  fireEvent.focus(input);fireEvent.change(input,{target:{value:"manager"}});
  expect(screen.getAllByRole("option")).toHaveLength(1);
  fireEvent.click(screen.getByRole("option",{name:/Ali.*Manager/}));
  expect((input as HTMLInputElement).value).toBe("Ali");
  fireEvent.click(screen.getByRole("button",{name:"Clear Contact"}));
  expect((input as HTMLInputElement).value).toBe("");
});

it("requires an actual record choice and supports choosing it with the keyboard",()=>{
  function Form(){const[value,set]=useState("");return <Combobox label="Required record" required value={value} onChange={set} options={[{id:"a",name:"Alpha"}]}/>;}
  ui(<Form/>);
  const input=screen.getByRole("combobox") as HTMLInputElement;
  fireEvent.change(input,{target:{value:"Alpha"}});
  expect(input.checkValidity()).toBe(false);
  fireEvent.keyDown(input,{key:"ArrowDown"});fireEvent.keyDown(input,{key:"Enter"});
  expect(input.value).toBe("Alpha");expect(input.checkValidity()).toBe(true);
});

it("cannot choose from an open popup after its parent fieldset becomes disabled",()=>{
  const changed=vi.fn();
  function Form(){const[disabled,set]=useState(false);return <><button onClick={()=>set(true)}>Saving</button><fieldset disabled={disabled}><Combobox label="Record" value="" onChange={changed} options={[{id:"a",name:"Alpha"}]}/></fieldset></>;}
  ui(<Form/>);fireEvent.focus(screen.getByRole("combobox"));
  fireEvent.click(screen.getByRole("button",{name:"Saving"}));
  fireEvent.click(screen.getByRole("option",{name:"Alpha"}));
  expect(changed).not.toHaveBeenCalled();
});
