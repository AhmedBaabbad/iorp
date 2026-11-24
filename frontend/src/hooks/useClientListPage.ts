"use client";
import {useEffect} from "react";
import {usePagedFilters} from "@/lib/pagination";

/** Only for small configuration catalogs (roles/permissions); operational records use server pagination. */
export function useClientListPage<T>(rows:T[],searchText:(row:T)=>string,ready=true,defaults:Record<string,string>={search:""},predicate?:(row:T,filters:Record<string,string>)=>boolean){
  const page=usePagedFilters(defaults),search=page.filters.search.trim().toLocaleLowerCase();
  const selected=predicate?rows.filter(row=>predicate(row,page.filters)):rows;
  const filtered=search?selected.filter(row=>searchText(row).toLocaleLowerCase().includes(search)):selected;
  const total=filtered.length,pages=Math.ceil(total/page.pageSize);
  const currentPage=page.page,setPage=page.setPage;
  useEffect(()=>{if(ready&&currentPage>Math.max(1,pages))setPage(Math.max(1,pages));},[ready,currentPage,pages,setPage]);
  return {...page,items:filtered.slice((page.page-1)*page.pageSize,page.page*page.pageSize),pagination:{page:page.page,pageSize:page.pageSize,total,pages,onPage:page.setPage,onPageSize:page.setPageSize}};
}
