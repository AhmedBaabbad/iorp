"use client";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useTranslations } from "next-intl";
import css from "./optional-date.module.css";

/** A date that may be left empty (a requested delivery, a due date, an end time…): it is set only when "Set a date" is
 *  ticked, and clearing the tick clears it, so an optional date is never mistaken for a required one nor kept by
 *  accident. Required dates stay plain inputs. Placed inside the field's label, whose text names both controls. */
export function OptionalDateInput({ value, onChange, label, type = "date", min, max, disabled, style }: {
  value: string; onChange: (value: string) => void; label: string; type?: "date" | "datetime-local";
  min?: string; max?: string; disabled?: boolean; style?: CSSProperties;
}) {
  const t = useTranslations("common.optionalDate");
  const [enabled, setEnabled] = useState(value !== "");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { if (value !== "") setEnabled(true); }, [value]);  // a saved date read after the first render
  function toggle(on: boolean) {
    setEnabled(on);
    if (!on) onChange("");
    else requestAnimationFrame(() => input.current?.focus());
  }
  return <span className={css.row}>
    <span className={css.toggle}>
      <input type="checkbox" checked={enabled} disabled={disabled} aria-label={`${t("set")}: ${label}`}
        onChange={event => toggle(event.target.checked)} />
      <span aria-hidden="true">{t("set")}</span>
    </span>
    {enabled ? <input ref={input} type={type} value={value} min={min} max={max} disabled={disabled} aria-label={label} style={style}
      className={css.input} onChange={event => onChange(event.target.value)} />
      : <span className={css.none}>{t("none")}</span>}
  </span>;
}
