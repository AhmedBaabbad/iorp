import type {Page} from "./pagination";

export type PageQuery = Record<string,string|number|boolean|undefined> & {page:string|number;page_size:string|number};
export function queryString(filters:object={}){
  const query=new URLSearchParams(Object.entries(filters).filter(([,value])=>value!==undefined&&value!==null&&value!=="").map(([key,value])=>[key,String(value)]));
  return query.size?`?${query}`:"";
}
/** Older array clients remain supported during a rolling deployment; new endpoints page on the server. */
export function readPage<T>(response:Page<T>|T[],page:number,pageSize:number):Page<T>{
  if(!Array.isArray(response))return response;
  return {items:response.slice((page-1)*pageSize,page*pageSize),total:response.length,page,page_size:pageSize,pages:Math.ceil(response.length/pageSize)};
}
