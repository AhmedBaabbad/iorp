/** Localized wording with the other language as fallback; legacy is for frozen historical documents. */
export function bilingualText(row:object,field:string,locale:string){
  const values=row as Record<string,unknown>;
  for(const key of [`${field}_${locale==="ar"?"ar":"en"}`,`${field}_${locale==="ar"?"en":"ar"}`,field]){
    const value=values[key];if(typeof value==="string"&&value.trim())return value;
  }
  return "";
}
