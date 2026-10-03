"use client";

import type { CSSProperties, FormEvent } from "react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createDefect } from "../api/quality-defects-api";
import type {
  CreateQualityDefectRequest,
  DefectCategory,
  DefectSeverity,
} from "../types";

type QualityDefectFormProps = {
  qualityCheckId: string;
  onCreated: () => Promise<void>;
  onCancel: () => void;
};

type QualityDefectFormValues = {
  defect_date: string;
  defect_category: DefectCategory;
  severity: DefectSeverity;
  defect_count: string;
  description: string;
  production_order_id: string;
  notes: string;
};

const styles: Record<string, CSSProperties> = {
  form: {
    display: "grid",
    gap: "16px",
  },
  formGrid: {
    display: "grid",
    gap: "16px",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  },
  actions: {
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
  },
  inlineError: {
    color: "var(--danger)",
    fontSize: "13px",
    margin: 0,
  },
};

function createDefaultValues(): QualityDefectFormValues {
  return {
    defect_date: new Date().toISOString().slice(0, 10),
    defect_category: "dimension",
    severity: "minor",
    defect_count: "1",
    description: "",
    production_order_id: "",
    notes: "",
  };
}

export function QualityDefectForm({
  qualityCheckId,
  onCreated,
  onCancel,
}: QualityDefectFormProps) {
  const t = useTranslations("quality.qualityChecks.defects");
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const [values, setValues] = useState<QualityDefectFormValues>(createDefaultValues);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [defectCountError, setDefectCountError] = useState<string | null>(null);
  const [descriptionError, setDescriptionError] = useState<string | null>(null);

  function updateField<TField extends keyof QualityDefectFormValues>(
    field: TField,
    value: QualityDefectFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));

    if (field === "defect_count") {
      setDefectCountError(null);
    }

    if (field === "description") {
      setDescriptionError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setDefectCountError(null);
    setDescriptionError(null);

    const defectCount = Number(values.defect_count);
    if (!Number.isInteger(defectCount) || defectCount < 1) {
      setDefectCountError(messages("validation.defectCountMin"));
      return;
    }

    if (!values.description.trim()) {
      setDescriptionError(messages("validation.descriptionRequired"));
      return;
    }

    setIsSubmitting(true);

    try {
      await createDefect(qualityCheckId, toCreateRequest(values));
      setValues(createDefaultValues());
      await onCreated();
    } catch (caughtError) {
      setFormError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form style={styles.form} onSubmit={handleSubmit}>
      <div style={styles.formGrid}>
        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>
            {t("fields.defectDate")} <span aria-hidden="true" style={{ color: "var(--danger)" }}>*</span>
          </span>
          <input
            style={sharedStyles.input}
            type="date"
            value={values.defect_date}
            onChange={(event) => updateField("defect_date", event.target.value)}
            disabled={isSubmitting}
            required
          />
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>
            {t("fields.defectCategory")} <span aria-hidden="true" style={{ color: "var(--danger)" }}>*</span>
          </span>
          <select
            style={sharedStyles.input}
            value={values.defect_category}
            onChange={(event) =>
              updateField("defect_category", event.target.value as DefectCategory)
            }
            disabled={isSubmitting}
            required
          >
            <option value="dimension">Dimension</option>
            <option value="thickness">Thickness / Gauge</option>
            <option value="surface">Surface Defect</option>
            <option value="color">Color Deviation</option>
            <option value="strength">Strength Failure</option>
            <option value="winding">Winding Defect</option>
            <option value="weight">Weight Out of Tolerance</option>
            <option value="packaging">Packaging Defect</option>
            <option value="labeling">Labeling Error</option>
            <option value="finish">Finish / Texture</option>
            <option value="other">Other</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>
            {t("fields.severity")} <span aria-hidden="true" style={{ color: "var(--danger)" }}>*</span>
          </span>
          <select
            style={sharedStyles.input}
            value={values.severity}
            onChange={(event) =>
              updateField("severity", event.target.value as DefectSeverity)
            }
            disabled={isSubmitting}
            required
          >
            <option value="minor">Minor</option>
            <option value="major">Major</option>
            <option value="critical">Critical</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>
            {t("fields.defectCount")} <span aria-hidden="true" style={{ color: "var(--danger)" }}>*</span>
          </span>
          <input
            style={sharedStyles.input}
            type="number"
            min="1"
            step="1"
            value={values.defect_count}
            onChange={(event) => updateField("defect_count", event.target.value)}
            disabled={isSubmitting}
            required
          />
          {defectCountError ? <p style={styles.inlineError}>{defectCountError}</p> : null}
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.productionOrderId")}</span>
          <input
            style={sharedStyles.input}
            value={values.production_order_id}
            onChange={(event) => updateField("production_order_id", event.target.value)}
            disabled={isSubmitting}
          />
        </label>
      </div>

      <label style={sharedStyles.field}>
        <span style={sharedStyles.label}>
          {t("fields.description")} <span aria-hidden="true" style={{ color: "var(--danger)" }}>*</span>
        </span>
        <textarea
          style={{ ...sharedStyles.textarea, minHeight: "100px" }}
          value={values.description}
          onChange={(event) => updateField("description", event.target.value)}
          disabled={isSubmitting}
          required
        />
        {descriptionError ? <p style={styles.inlineError}>{descriptionError}</p> : null}
      </label>

      <label style={sharedStyles.field}>
        <span style={sharedStyles.label}>{t("fields.notes")}</span>
        <textarea
          style={sharedStyles.textarea}
          value={values.notes}
          onChange={(event) => updateField("notes", event.target.value)}
          disabled={isSubmitting}
        />
      </label>

      {formError ? (
        <div style={sharedStyles.error} role="alert">
          {formError}
        </div>
      ) : null}

      <div style={styles.actions}>
        <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
          {isSubmitting ? t("saving") : t("saveButton")}
        </button>
        <button
          style={sharedStyles.secondaryButton}
          type="button"
          disabled={isSubmitting}
          onClick={onCancel}
        >
          {common("actions.cancel")}
        </button>
      </div>
    </form>
  );
}

function toCreateRequest(values: QualityDefectFormValues): CreateQualityDefectRequest {
  return {
    production_order_id: optionalText(values.production_order_id) ?? null,
    defect_date: values.defect_date,
    defect_category: values.defect_category,
    severity: values.severity,
    defect_count: Number(values.defect_count),
    description: values.description.trim(),
    notes: optionalText(values.notes) ?? null,
  };
}
