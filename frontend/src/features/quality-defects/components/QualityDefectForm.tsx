"use client";

import type { CSSProperties, FormEvent } from "react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { lifecycleErrorCode } from "@/features/production-demands/planning-lifecycle";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createDefects } from "../api/quality-defects-api";
import type { CreateQualityDefectRequest, DefectCategory, DefectSeverity } from "../types";

const CATEGORIES: DefectCategory[] = ["dimension", "thickness", "surface", "color", "strength", "winding", "weight", "packaging", "labeling", "finish", "other"];
const SEVERITIES: DefectSeverity[] = ["minor", "major", "critical"];

type QualityDefectFormProps = {
  qualityCheckId: string;
  // Defect types already recorded on this inspection: each type is recorded once (more go in its count).
  recordedCategories?: DefectCategory[];
  onCreated: () => Promise<void>;
  onCancel: () => void;
};

type Row = { key: number; defect_category: DefectCategory | ""; severity: DefectSeverity; defect_count: string; description: string };

const styles: Record<string, CSSProperties> = {
  form: { display: "grid", gap: "16px" },
  row: { display: "grid", gap: "12px", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", alignItems: "end",
    padding: "12px", border: "1px solid var(--border)", borderRadius: "8px" },
  actions: { display: "flex", flexWrap: "wrap", gap: "12px" },
  inlineError: { color: "var(--danger)", fontSize: "13px", margin: 0 },
};

let nextKey = 1;
const newRow = (category: DefectCategory | "" = ""): Row => ({ key: nextKey++, defect_category: category, severity: "minor", defect_count: "1", description: "" });

// Several defects found on one inspection, recorded together (all or none). Each type once per inspection.
export function QualityDefectForm({ qualityCheckId, recordedCategories = [], onCreated, onCancel }: QualityDefectFormProps) {
  const t = useTranslations("quality.qualityChecks.defects");
  const enumT = useTranslations("enums");
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [rows, setRows] = useState<Row[]>(() => [newRow(CATEGORIES.find(c => !recordedCategories.includes(c)) ?? "")]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});

  const taken = (row: Row) => new Set([...recordedCategories, ...rows.filter(r => r.key !== row.key).map(r => r.defect_category)]);
  const free = CATEGORIES.filter(c => !recordedCategories.includes(c) && !rows.some(r => r.defect_category === c));
  const update = (key: number, patch: Partial<Row>) => {
    setRows(current => current.map(r => (r.key === key ? { ...r, ...patch } : r)));
    setRowErrors(current => { const next = { ...current }; delete next[key]; return next; });
  };

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    const errors: Record<number, string> = {};
    for (const row of rows) {
      const count = Number(row.defect_count);
      if (!row.defect_category) errors[row.key] = t("validation.categoryRequired");
      else if (!Number.isInteger(count) || count < 1) errors[row.key] = messages("validation.defectCountMin");
      else if (!row.description.trim()) errors[row.key] = messages("validation.descriptionRequired");
    }
    setRowErrors(errors);
    if (Object.keys(errors).length || !rows.length) return;
    setIsSubmitting(true);
    try {
      await createDefects(qualityCheckId, rows.map(row => toCreateRequest(row, date, notes)));
      setRows([newRow()]);
      setNotes("");
      await onCreated();
    } catch (caughtError) {
      const code = lifecycleErrorCode(caughtError);
      setFormError(t.has(`errors.${code}`) ? t(`errors.${code}`) : getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form style={styles.form} onSubmit={handleSubmit} aria-label={t("formTitle")}>
      <label style={{ ...sharedStyles.field, maxWidth: "240px" }}>
        <span style={sharedStyles.label}>{t("fields.defectDate")} <span aria-hidden="true" style={{ color: "var(--danger)" }}>*</span></span>
        <input style={sharedStyles.input} type="date" value={date} onChange={e => setDate(e.target.value)} disabled={isSubmitting} required />
      </label>
      <p style={{ margin: 0, color: "var(--text-muted)" }}>{t("onePerType")}</p>

      {rows.map((row, index) => (
        <fieldset key={row.key} style={styles.row} disabled={isSubmitting} aria-label={t("defectNumber", { number: index + 1 })}>
          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.defectCategory")}</span>
            <select style={sharedStyles.input} value={row.defect_category} required
              onChange={e => update(row.key, { defect_category: e.target.value as DefectCategory })}>
              <option value="">{t("chooseCategory")}</option>
              {CATEGORIES.map(c => <option key={c} value={c} disabled={taken(row).has(c)}>{enumT(`qualityDefect.defectCategory.${c}`)}</option>)}
            </select>
          </label>
          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.severity")}</span>
            <select style={sharedStyles.input} value={row.severity} onChange={e => update(row.key, { severity: e.target.value as DefectSeverity })}>
              {SEVERITIES.map(s => <option key={s} value={s}>{enumT(`qualityDefect.severity.${s}`)}</option>)}
            </select>
          </label>
          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.defectCount")}</span>
            <input style={sharedStyles.input} type="number" min="1" step="1" value={row.defect_count} required
              onChange={e => update(row.key, { defect_count: e.target.value })} />
          </label>
          <label style={{ ...sharedStyles.field, gridColumn: "span 2" }}>
            <span style={sharedStyles.label}>{t("fields.description")}</span>
            <input style={sharedStyles.input} value={row.description} required onChange={e => update(row.key, { description: e.target.value })} />
          </label>
          {rows.length > 1 && <button type="button" style={sharedStyles.secondaryButton} onClick={() => setRows(current => current.filter(r => r.key !== row.key))}>
            {t("removeDefect")}</button>}
          {rowErrors[row.key] ? <p style={{ ...styles.inlineError, gridColumn: "1 / -1" }} role="alert">{rowErrors[row.key]}</p> : null}
        </fieldset>
      ))}

      {free.length > 0 && <button type="button" style={{ ...sharedStyles.secondaryButton, width: "fit-content" }} disabled={isSubmitting}
        onClick={() => setRows(current => [...current, newRow(free[0])])}>{t("addAnother")}</button>}

      <label style={sharedStyles.field}>
        <span style={sharedStyles.label}>{t("fields.notes")}</span>
        <textarea style={sharedStyles.textarea} value={notes} onChange={e => setNotes(e.target.value)} disabled={isSubmitting} />
      </label>

      {formError ? <div style={sharedStyles.error} role="alert">{formError}</div> : null}

      <div style={styles.actions}>
        <button style={sharedStyles.button} type="submit" disabled={isSubmitting || !rows.length}>
          {isSubmitting ? t("saving") : t("saveDefects", { count: rows.length })}
        </button>
        <button style={sharedStyles.secondaryButton} type="button" disabled={isSubmitting} onClick={onCancel}>{common("actions.cancel")}</button>
      </div>
    </form>
  );
}

function toCreateRequest(row: Row, date: string, notes: string): CreateQualityDefectRequest {
  return {
    production_order_id: null,
    defect_date: date,
    defect_category: row.defect_category as DefectCategory,
    severity: row.severity,
    defect_count: Number(row.defect_count),
    description: row.description.trim(),
    notes: optionalText(notes) ?? null,
  };
}
