"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { sharedStyles } from "@/styles/shared-styles";

import { rowsToSpec, specToRows, templateSpec, type Row, type SpecTemplateProperty } from "@/lib/spec-rows";

function split(value: string, template: SpecTemplateProperty[]): { values: Record<string, string>; extra: Row[] } {
  const known = new Set(template.map(p => p.key));
  const rows = specToRows(value);
  return { values: Object.fromEntries(rows.filter(r => known.has(r.key)).map(r => [r.key, r.value])), extra: rows.filter(r => !known.has(r.key)) };
}

/**
 * The line's specification. With the product's template (master data, MD-001) it is the template's properties in order —
 * a number with its unit, a text, or a choice — followed by any extra "property | value" rows; without one, rows only.
 * Stored as JSON (quotation and shipment lines alike), so commercial orders and production read it unchanged.
 */
export function SpecEditor({ value, onChange, disabled, template }: {
  value: string; onChange: (json: string) => void; disabled?: boolean; template?: SpecTemplateProperty[] | null;
}) {
  const t = useTranslations("common.spec");
  const units = useTranslations("common.units.units");
  const locale = useLocale();
  const props = template ?? [];
  const [values, setValues] = useState<Record<string, string>>(() => split(value, props).values);
  const [rows, setRows] = useState<Row[]>(() => split(value, props).extra);
  const emitted = useRef(value);
  const shape = props.map(p => p.key).join("|");

  // A value loaded later (edit form) or another product's template replaces the fields; our own edits do not.
  useEffect(() => {
    if (value !== emitted.current) {
      emitted.current = value;
      const next = split(value, props);
      setValues(next.values); setRows(next.extra);
    }
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const next = split(emitted.current, props);
    setValues(next.values); setRows(next.extra);
  }, [shape]); // eslint-disable-line react-hooks/exhaustive-deps

  function emit(nextValues: Record<string, string>, nextRows: Row[]) {
    setValues(nextValues); setRows(nextRows);
    const json = props.length ? templateSpec(props, nextValues, nextRows) : rowsToSpec(nextRows);
    emitted.current = json;
    onChange(json);
  }
  const label = (p: SpecTemplateProperty) => `${locale === "ar" ? p.name_ar : p.name_en}${p.unit ? ` (${units.has(p.unit) ? units(p.unit) : p.unit})` : ""}${p.required ? " *" : ""}`;

  return (
    <fieldset style={{ border: "1px solid var(--border)", borderRadius: "8px", padding: "12px", display: "grid", gap: "8px" }}>
      <legend style={{ padding: "0 6px", fontWeight: 600 }}>{t("title")}</legend>
      {props.length ? (
        <div style={{ display: "grid", gap: "10px", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
          {props.map(p => (
            <label key={p.key} style={sharedStyles.field}><span style={sharedStyles.label}>{label(p)}</span>
              {p.kind === "choice" ? (
                <select style={sharedStyles.input} value={values[p.key] ?? ""} disabled={disabled} required={p.required}
                  onChange={(e) => emit({ ...values, [p.key]: e.target.value }, rows)}>
                  <option value="">—</option>
                  {(p.options ?? []).map(o => <option key={o.value} value={o.value}>{locale === "ar" ? o.label_ar : o.label_en}</option>)}
                </select>
              ) : (
                <input style={sharedStyles.input} value={values[p.key] ?? ""} disabled={disabled} required={p.required} maxLength={200}
                  inputMode={p.kind === "number" ? "decimal" : undefined} dir={p.kind === "number" ? "ltr" : undefined}
                  pattern={p.kind === "number" ? "-?\\d+(\\.\\d+)?" : undefined}
                  onChange={(e) => emit({ ...values, [p.key]: e.target.value }, rows)} />
              )}
            </label>
          ))}
        </div>
      ) : null}
      {props.length ? <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>{t("extra")}</span>
        : !rows.length ? <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "13px" }}>{t("empty")}</p> : null}
      {rows.map((row, index) => (
        <div key={index} style={{ display: "grid", gridTemplateColumns: "minmax(120px, 1fr) minmax(120px, 1.4fr) auto", gap: "8px" }}>
          <input style={sharedStyles.input} aria-label={t("property")} placeholder={t("propertyHint")} value={row.key} maxLength={200} disabled={disabled}
            onChange={(event) => emit(values, rows.map((r, i) => (i === index ? { ...r, key: event.target.value } : r)))} />
          <input style={sharedStyles.input} aria-label={t("value")} placeholder={t("valueHint")} value={row.value} maxLength={200} disabled={disabled}
            onChange={(event) => emit(values, rows.map((r, i) => (i === index ? { ...r, value: event.target.value } : r)))} />
          <button type="button" style={sharedStyles.secondaryButton} disabled={disabled} aria-label={t("remove")}
            onClick={() => emit(values, rows.filter((_, i) => i !== index))}>×</button>
        </div>
      ))}
      <div><button type="button" style={sharedStyles.secondaryButton} disabled={disabled}
        onClick={() => setRows([...rows, { key: "", value: "" }])}>{t("add")}</button></div>
    </fieldset>
  );
}
