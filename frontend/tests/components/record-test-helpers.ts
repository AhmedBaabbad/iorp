import {fireEvent,screen,waitFor,type ByRoleOptions} from "@testing-library/react";

/** Select an identifier through the visible popup; native enum controls still use change. */
export function changeControl(element:Element|Document|Window,init?:{target?:{value?:unknown;[key:string]:unknown};[key:string]:unknown}){
  if(element instanceof HTMLInputElement&&element.getAttribute("role")==="combobox"){
    if(element.getAttribute("aria-expanded")!=="true")fireEvent.focus(element);
    const option=document.getElementById(`${element.id}-${String(init?.target?.value??"")}`);
    if(option?.getAttribute("role")==="option"){fireEvent.click(option);return true;}
  }
  return fireEvent.change(element,init);
}

/** Old tests awaited always-visible native options; searchable lists must first be opened. */
export async function findRecordOption(name:ByRoleOptions["name"],options?:ByRoleOptions){
  const existing=screen.queryByRole("option",{name,...options});if(existing)return existing;
  return waitFor(()=>{
    for(const input of screen.queryAllByRole("combobox")){
      if(input instanceof HTMLInputElement&&!input.disabled){
        if(input.getAttribute("aria-expanded")!=="true")fireEvent.focus(input);
        const option=screen.queryByRole("option",{name,...options});
        if(option)return option;
      }
    }
    return screen.getByRole("option",{name,...options});
  });
}

export function recordOptions(input:HTMLSelectElement|HTMLInputElement){
  if(input instanceof HTMLSelectElement)return Array.from(input.options);
  if(input.getAttribute("aria-expanded")!=="true")fireEvent.focus(input);
  return Array.from(document.getElementById(`${input.id}-options`)?.querySelectorAll('[role="option"]')??[])
    .map(option=>({textContent:option.textContent,value:option.id.slice(input.id.length+1)}));
}
