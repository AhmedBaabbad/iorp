"use client";
import {Children,isValidElement,useRef,useState,type ReactNode,type CSSProperties} from "react";
import {useTranslations} from "next-intl";
import {Combobox,type ComboOption} from "./Combobox";

function text(node:ReactNode):string {
  if(typeof node==="string"||typeof node==="number")return String(node);
  if(isValidElement<{children?:ReactNode}>(node))return text(node.props.children);
  return Array.isArray(node)?node.map(text).join(""):"";
}
function optionsFrom(children:ReactNode,group?:string):ComboOption[]{
  return Children.toArray(children).flatMap(node=>{
    if(!isValidElement<{children?:ReactNode;value?:string|number;disabled?:boolean;label?:string}>(node))return [];
    if(node.type==="option")return [{id:String(node.props.value??text(node.props.children)),name:text(node.props.children),detail:group,disabled:node.props.disabled}];
    return optionsFrom(node.props.children,node.type==="optgroup"?node.props.label:group);
  });
}

/** Projects existing API option labels into the single searchable record control. No native select is rendered. */
export function RecordCombobox({value:controlledValue,defaultValue="",onChange,children,"aria-label":ariaLabel,id,disabled,required,style,className,autoFocus,title,name,onSearch,loading}:{
  value?:string|number|null;defaultValue?:string;onChange?:(value:string)=>void;children:ReactNode;"aria-label"?:string;
  id?:string;disabled?:boolean;required?:boolean;style?:CSSProperties;className?:string;autoFocus?:boolean;title?:string;name?:string;
  onSearch?:(query:string)=>void;loading?:boolean;
}){
  const t=useTranslations("directory");
  const [localValue,setLocalValue]=useState(defaultValue);
  const value=controlledValue===undefined?localValue:controlledValue;
  const options=optionsFrom(children),empty=options.find(option=>option.id==="");
  const held=useRef<ComboOption|undefined>(undefined),current=options.find(option=>option.id===String(value??""));
  if(current)held.current=current;
  const shown=!current&&held.current?.id===String(value??"")?[...options,held.current]:options;
  const label=ariaLabel??empty?.name??t("searchChoose");
  return <Combobox label={label} hideLabel id={id} ariaLabel={label} value={value==null?"":String(value)} options={shown}
    onChange={next=>{setLocalValue(next);onChange?.(next);}} disabled={disabled} required={required} style={style} className={className} autoFocus={autoFocus}
    placeholder={empty?.name} title={title} name={name} onSearch={onSearch} loading={loading}/>;
}
