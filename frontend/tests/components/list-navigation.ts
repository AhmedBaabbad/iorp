import {useSyncExternalStore} from "react";

// A URL-backed App Router test double: replace notifies mounted URL consumers.
const subscribe=(notify:()=>void)=>{window.addEventListener("popstate",notify);return()=>window.removeEventListener("popstate",notify);};
export const listRouter={
  replace(path:string){window.history.replaceState(null,"",path);window.dispatchEvent(new PopStateEvent("popstate"));},
  push(path:string){window.history.pushState(null,"",path);window.dispatchEvent(new PopStateEvent("popstate"));},
  refresh(){},
};
export function useListSearchParams(){
  const query=useSyncExternalStore(subscribe,()=>window.location.search,()=>"");
  return new URLSearchParams(query);
}
export const listNavigation={useRouter:()=>listRouter,usePathname:()=>window.location.pathname,useSearchParams:useListSearchParams};
