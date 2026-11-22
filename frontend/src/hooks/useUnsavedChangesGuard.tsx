"use client";
import {useEffect,useRef,useState} from "react";
import {useRouter} from "next/navigation";
import {useTranslations} from "next-intl";
import {Dialog} from "@/components/ui/Dialog";
import s from "@/features/production-demands/demands.module.css";

/** Protect browser refresh/close and same-tab links, including sidebar and Back/Cancel links. */
export function useUnsavedChangesGuard(dirty:boolean){
  const t=useTranslations("common.unsavedChanges"),router=useRouter();
  const approved=useRef(false),current=useRef(dirty);
  if(!dirty)approved.current=false;
  current.current=dirty&&!approved.current;
  const [destination,setDestination]=useState<string|(()=>void)|null>(null);
  useEffect(()=>{
    const beforeUnload=(event:BeforeUnloadEvent)=>{if(current.current){event.preventDefault();event.returnValue="";}};
    const click=(event:MouseEvent)=>{
      if(!current.current||event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
      const anchor=event.target instanceof Element?event.target.closest<HTMLAnchorElement>("a[href]"):null;
      if(!anchor||anchor.target==="_blank"||anchor.hasAttribute("download"))return;
      const target=new URL(anchor.href,window.location.href),here=new URL(window.location.href);
      if(!["http:","https:"].includes(target.protocol)||(target.pathname===here.pathname&&target.search===here.search&&target.origin===here.origin))return;
      event.preventDefault();event.stopImmediatePropagation();setDestination(target.href);
    };
    window.addEventListener("beforeunload",beforeUnload);document.addEventListener("click",click,true);
    return()=>{window.removeEventListener("beforeunload",beforeUnload);document.removeEventListener("click",click,true);};
  },[]);
  const allowNavigation=()=>{approved.current=true;current.current=false;};
  const confirmation=destination?<Dialog role="alertdialog" title={t("title")} onClose={()=>setDestination(null)} footer={<>
    <button type="button" className={s.button} onClick={()=>setDestination(null)} autoFocus>{t("stay")}</button>
    <button type="button" className={`${s.button} ${s.danger}`} onClick={()=>{
      approved.current=true;current.current=false;setDestination(null);
      if(typeof destination==="function"){destination();return;}
      const target=new URL(destination);
      if(target.origin===window.location.origin)router.push(target.pathname+target.search+target.hash);else window.location.assign(target.href);
    }}>{t("leave")}</button>
  </>}><p>{t("message")}</p></Dialog>:null;
  const requestNavigation=(action:()=>void)=>{if(current.current)setDestination(()=>action);else action();};
  return {confirmation,allowNavigation,requestNavigation};
}

/** The snapshot contains only editable data, not lookups, loading flags or search text. */
export function useUnsavedFormChanges(snapshot:unknown,ready=true){
  const [,redraw]=useState(0);
  const serialized=JSON.stringify(snapshot),baseline=useRef(serialized),touched=useRef(false);
  // Initial lookups may fill defaults. They become the baseline until the user interacts.
  if(!touched.current||!ready)baseline.current=serialized;
  const guard=useUnsavedChangesGuard(ready&&touched.current&&baseline.current!==serialized);
  return {...guard,
    onInteraction:()=>{touched.current=true;},
    onKeyboardInteraction:(event:{key:string})=>{if(!["Tab","Shift","Control","Alt","Meta","Escape"].includes(event.key))touched.current=true;},
    markSaved:()=>{baseline.current=serialized;touched.current=false;guard.allowNavigation();redraw(value=>value+1);},
  };
}
