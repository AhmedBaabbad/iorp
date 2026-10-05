"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { sharedStyles } from "@/styles/shared-styles";

import { rowsToSpec, specToRows, type Row } from "@/lib/spec-rows";

/**
 * The line's specification as "property | value" rows (width, thickness, colour, weight...), any properties a
 * product needs. Stored as JSON (quotation and shipment lines alike), so commercial orders and production read it unchanged.
 */
export function SpecEditor({ value, onChange, disabled }: { value: string; onChange: (json: string) => void; disabled?: boolean }) {
  const t = useTranslations("common.spec");
  const [rows, setRows] = useState<Row[]>(() => specToRows(value));
  const emitted = useRef(value);

  // A value loaded later (edit form) replaces the rows; our own edits do not.
  useEffect(() => {
    if (value !== emitted.current) { emitted.current = value; setRows(specToRows(value)); }
  }, [value]);

  function update(next: Row[]) {
    setRows(next);
    const json = rowsToSpec(next);
    emitted.current = json;
    onChange(json);
  }

  return (
    <fieldset style={{ border: "1px solid var(--border)", borderRadius: "8px", padding: "12px", display: "grid", gap: "8px" }}>
      <legend style={{ padding: "0 6px", fontWeight: 600 }}>{t("title")}</legend>
      {!rows.length ? <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "13px" }}>{t("empty")}</p> : null}
      {rows.map((row, index) => (
        <div key={index} style={{ display: "grid", gridTemplateColumns: "minmax(120px, 1fr) minmax(120px, 1.4fr) auto", gap: "8px" }}>
          <input style={sharedStyles.input} aria-label={t("property")} placeholder={t("propertyHint")} value={row.key} maxLength={60} disabled={disabled}
            onChange={(event) => update(rows.map((r, i) => (i === index ? { ...r, key: event.target.value } : r)))} />
          <input style={sharedStyles.input} aria-label={t("value")} placeholder={t("valueHint")} value={row.value} maxLength={200} disabled={disabled}
            onChange={(event) => update(rows.map((r, i) => (i === index ? { ...r, value: event.target.value } : r)))} />
          <button type="button" style={sharedStyles.secondaryButton} disabled={disabled} aria-label={t("remove")}
            onClick={() => update(rows.filter((_, i) => i !== index))}>×</button>
        </div>
      ))}
      <div><button type="button" style={sharedStyles.secondaryButton} disabled={disabled}
        onClick={() => setRows([...rows, { key: "", value: "" }])}>{t("add")}</button></div>
    </fieldset>
  );
}
