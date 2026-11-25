"use client";
import {useCallback,useEffect,useMemo,useRef,useState} from "react";
import {usePagedFilters,type Page} from "@/lib/pagination";
import {readPage,type PageQuery} from "@/lib/page-response";

/** URL filters plus metadata; legacy array responses are supported during a rolling deployment. */
export function useListPage<T,F extends Record<string,string|boolean>=Record<string,string>>(defaults:F,aliases:Record<string,keyof F & string>={},scope=""){
  const paged=usePagedFilters(defaults,aliases),serialized=JSON.stringify(paged.query()),key=`${scope}\0${serialized}`;
  const params=useMemo(()=>JSON.parse(serialized) as PageQuery,[serialized]);
  const latest=useRef(key);
  useEffect(()=>{latest.current=key;},[key]);
  const [meta,setMeta]=useState<Page<T>|null>(null);
  const [acceptedKey,setAcceptedKey]=useState<string|null>(null);
  const page=paged.page,pageSize=paged.pageSize;
  const setPage=paged.setPage;
  const accept=useCallback((response:Page<T>|T[],setRows:(rows:T[])=>void)=>{
    if(latest.current!==key)return;
    const result=readPage(response,page,pageSize);setMeta(result);setAcceptedKey(key);setRows(result.items);
  },[key,page,pageSize]);
  useEffect(()=>{
    if(meta&&acceptedKey===key&&meta.page===page&&meta.page_size===pageSize&&page>Math.max(1,meta.pages))setPage(Math.max(1,meta.pages));
  },[meta,acceptedKey,key,page,pageSize,setPage]);
  return {...paged,key,params,accept,meta,pending:acceptedKey!==key,hasFilters:Object.values(paged.filters).some(Boolean),pagination:{page,pageSize,total:meta?.total??0,pages:meta?.pages??0,onPage:paged.setPage,onPageSize:paged.setPageSize}};
}
