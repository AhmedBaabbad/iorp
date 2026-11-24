"use client";
import { useEffect, useRef, useState, type InputHTMLAttributes } from "react";
import { useTranslations } from "next-intl";
import { formatSpecValue, parseNumericSpec, SpecValueError } from "@/lib/spec-value";

export function NumericSpecInput({ value, onValueChange, allowsRange = false, onBlur, ...props }: Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> & {
  value: unknown; onValueChange: (text: string) => void; allowsRange?: boolean;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const t = useTranslations("common.spec");
  const text = formatSpecValue(value);
  const [touched,setTouched]=useState(false);
  let error = "";
  if (text.trim()) try { parseNumericSpec(text, allowsRange); } catch (e) {
    error = t(e instanceof SpecValueError ? e.code : "SPEC_RANGE_NUMBER");
  }
  useEffect(() => { ref.current?.setCustomValidity(error); }, [error]);
  return <><input {...props} ref={ref} type="text" inputMode="decimal" dir="ltr" value={text}
    aria-invalid={touched&&Boolean(error)} onBlur={event=>{setTouched(true);onBlur?.(event);}} onChange={e => {setTouched(false);onValueChange(e.target.value);}} />
    {touched&&error && <small role="alert" style={{ color: "var(--danger)" }}>{error}</small>}</>;
}
