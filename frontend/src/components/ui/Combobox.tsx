"use client";
import { useEffect, useId, useRef, useState, type CSSProperties } from "react";
import { useTranslations } from "next-intl";
import css from "./records.module.css";

export type ComboOption = { id: string; name: string; detail?: string; disabled?: boolean };
export function Combobox<T extends ComboOption>({ label, value, options, onChange, onSearch, loading = false,
  disabled = false, required = false, error, hideLabel = false, ariaLabel, id: suppliedId, style, className, placeholder, autoFocus, title, name }: {
  label: string; value?: string | null; options: T[]; onChange: (id: string, option?: T) => void;
  onSearch?: (query: string) => void; loading?: boolean; disabled?: boolean; required?: boolean; error?: string;
  hideLabel?: boolean; ariaLabel?: string; id?: string; style?: CSSProperties; className?: string; placeholder?: string;
  autoFocus?: boolean; title?: string; name?: string;
}) {
  const t = useTranslations("directory");
  const generatedId = useId(), id = suppliedId ?? generatedId, root = useRef<HTMLDivElement>(null), input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false), [index, setIndex] = useState(-1);
  const selected = value ? options.find(option => option.id === value) : undefined;
  const found = onSearch ? options : options.filter(option => `${option.name} ${option.detail ?? ""}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  useEffect(() => {
    const close = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", close); return () => document.removeEventListener("pointerdown", close);
  }, []);
  useEffect(()=>{input.current?.setCustomValidity(required&&!value?t("searchChoose"):"");},[required,value,t]);
  function choose(option: T) { if(option.disabled||disabled||input.current?.matches(":disabled"))return; onChange(option.id, option); setOpen(false); setQuery(""); setIndex(-1); }
  return <div ref={root} className={css.combo}>
    {!hideLabel&&<label htmlFor={id}>{label}</label>}
    <div className={css.comboControl}>
      <input ref={input} id={id} role="combobox" autoComplete="off" aria-autocomplete="list" aria-expanded={open}
        aria-label={ariaLabel??label} style={style} className={className} autoFocus={autoFocus} title={title}
        aria-controls={`${id}-options`} aria-activedescendant={open && index >= 0 && found[index] ? `${id}-${found[index].id}` : undefined}
        disabled={disabled} required={required && !value} value={open ? query : selected?.name ?? (value ? t("savedSelection") : "")}
        placeholder={placeholder??t("searchChoose")} onFocus={() => {setOpen(true);setQuery("");setIndex(-1);onSearch?.("");}}
        onChange={event => {setQuery(event.target.value);setOpen(true);setIndex(-1);onSearch?.(event.target.value);}}
        onBlur={event => {if (!root.current?.contains(event.relatedTarget as Node)) setOpen(false);}}
        onKeyDown={event => {
          if (event.key === "Escape" && open) {event.preventDefault(); event.stopPropagation(); setOpen(false);return;}
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault(); setOpen(true);
            setIndex(old => {const direction=event.key==="ArrowDown"?1:-1;let next=old<0?(direction===1?-1:0):old;
              for(let n=0;n<found.length;n++){next=(next+direction+found.length)%found.length;if(!found[next].disabled)return next;}return -1;});
          } else if (event.key === "Enter" && open) {
            event.preventDefault(); if (found[index]) choose(found[index]);
          }
        }}/>
      {value && <button type="button" disabled={disabled} aria-label={t("clear", { label })} onClick={() => {onChange("");setQuery("");setOpen(false);onSearch?.("");}}>×</button>}
    </div>
    {open && <ul role="listbox" id={`${id}-options`} aria-label={t("searchResults",{label})} className={css.options}>
      {found.map((option, n) => <li role="option" id={`${id}-${option.id}`} key={option.id} aria-selected={value === option.id} aria-disabled={option.disabled||undefined}
        className={index === n ? css.highlight : undefined} onPointerDown={event => event.preventDefault()}
        onMouseDown={event => event.preventDefault()} onClick={() => choose(option)}>
        <span>{option.name}</span>{option.detail && <small>{option.detail}</small>}
      </li>)}
      {found.length === 0 && <li role="presentation">{loading ? t("loading") : t("noResults")}</li>}
    </ul>}
    {name && <input type="hidden" name={name} value={value??""} disabled={disabled}/>}
    {error && <span role="alert" className={css.error}>{error}</span>}
  </div>;
}
