"use client";
import {useLocale} from "next-intl";
import {formatUnit} from "@/lib/localized-units";
export function UnitLabel({value}:{value:string|null|undefined}){return <>{formatUnit(value,useLocale())}</>;}

export function useUnitLabel(){const locale=useLocale();return (value:string|null|undefined)=>formatUnit(value,locale);}
