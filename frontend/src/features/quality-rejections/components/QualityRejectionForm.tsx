"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import type { CSSProperties, FormEvent } from "react";
import { useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createQualityRejection } from "../api/quality-rejections-api";
import type {
  CreateQualityRejectionRequest,
  Disposition,
  RejectionReason,
} from "../types";

type QualityRejectionFormValues = {
  rejection_date: string;
  rejection_reason: RejectionReason;
  rejection_notes: string;
  disposition: Disposition;
  quantity_rejected: string;
  unit: string;
  quality_check_id: string;
  quality_defect_id: string;
  production_output_id: string;
  production_order_item_id: string;
  notes: string;
};

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
  },
  form: {
    display: "grid",
    gap: "18px",
    padding: "24px",
  },
  formGrid: {
    display: "grid",
    gap: "18px",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  },
  actions: {
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
    alignItems: "center",
  },
  inlineError: {
    color: "var(--danger)",
    fontSize: "13px",
    margin: 0,
  },
  warning: {
    background: "var(--warning-soft)",
    border: "1px solid color-mix(in srgb, var(--warning) 35%, var(--surface))",
    borderRadius: "6px",
    color: "var(--warning)",
    fontSize: "14px",
    padding: "12px 14px",
  },
};

const defaultValues: QualityRejectionFormValues = {
  rejection_date: new Date().toISOString().slice(0, 10),
  rejection_reason: "failed_quality_check",
  rejection_notes: "",
  disposition: "hold",
  quantity_rejected: "",
  unit: "kg",
  quality_check_id: "",
  quality_defect_id: "",
  production_output_id: "",
  production_order_item_id: "",
  notes: "",
};

export function QualityRejectionForm() {
  const t = useTranslations("quality.qualityRejections");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const router = useRouter();
  const [values, setValues] = useState<QualityRejectionFormValues>(defaultValues);
  const [quantityError, setQuantityError] = useState<string | null>(null);
  const [notesError, setNotesError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasQualityReference =
    values.quality_check_id.trim().length > 0 ||
    values.quality_defect_id.trim().length > 0;

  function updateField<TField extends keyof QualityRejectionFormValues>(
    field: TField,
    value: QualityRejectionFormValues[TField],
  ) {
    setValues((current) => ({ ...current, [field]: value }));

    if (field === "quantity_rejected") {
      setQuantityError(null);
    }

    if (field === "rejection_notes") {
      setNotesError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setQuantityError(null);
    setNotesError(null);

    if (Number(values.quantity_rejected) <= 0) {
      setQuantityError(t("quantityRejectedPositive"));
      return;
    }

    if (!values.rejection_notes.trim()) {
      setNotesError(t("rejectionJustificationRequired"));
      return;
    }

    setIsSubmitting(true);

    try {
      const createdRejection = await createQualityRejection(toCreateRequest(values));
      router.replace(`/quality-rejections/${createdRejection.id}`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <PageFrame
      section="Quality"
      title={t("createTitle")}
      subtitle={t("createSubtitle")}
      action={
        <Link href="/quality-rejections" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      <section style={styles.panel}>
        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={styles.formGrid}>
            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.rejectionDate")} *</span>
              <input
                style={sharedStyles.input}
                type="date"
                value={values.rejection_date}
                onChange={(event) => updateField("rejection_date", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.rejectionReason")} *</span>
              <select
                style={sharedStyles.input}
                value={values.rejection_reason}
                onChange={(event) =>
                  updateField("rejection_reason", event.target.value as RejectionReason)
                }
                disabled={isSubmitting}
                required
              >
                <option value="failed_quality_check">Failed Quality Check</option>
                <option value="critical_defect">Critical Defect</option>
                <option value="out_of_spec">Out of Specification</option>
                <option value="dimension_failure">Dimension Failure</option>
                <option value="surface_failure">Surface Failure</option>
                <option value="packaging_failure">Packaging Failure</option>
                <option value="labeling_issue">Labeling Issue</option>
                <option value="other">Other</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.disposition")} *</span>
              <select
                style={sharedStyles.input}
                value={values.disposition}
                onChange={(event) =>
                  updateField("disposition", event.target.value as Disposition)
                }
                disabled={isSubmitting}
                required
              >
                <option value="hold">Hold (Quarantine)</option>
                <option value="scrap">Scrap (Discard)</option>
                <option value="rework">Rework (Fix and Re-inspect)</option>
                <option value="return_to_process">Return to Process</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.quantityRejected")} *</span>
              <input
                style={sharedStyles.input}
                type="number"
                min="1"
                step="1"
                value={values.quantity_rejected}
                onChange={(event) => updateField("quantity_rejected", event.target.value)}
                disabled={isSubmitting}
                required
              />
              {quantityError ? <p style={styles.inlineError}>{quantityError}</p> : null}
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.unit")} *</span>
              <input
                style={sharedStyles.input}
                value={values.unit}
                onChange={(event) => updateField("unit", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.qualityCheckId")}</span>
              <input
                style={sharedStyles.input}
                value={values.quality_check_id}
                onChange={(event) => updateField("quality_check_id", event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.qualityDefectId")}</span>
              <input
                style={sharedStyles.input}
                value={values.quality_defect_id}
                onChange={(event) => updateField("quality_defect_id", event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.productionOutputId")}</span>
              <input
                style={sharedStyles.input}
                value={values.production_output_id}
                onChange={(event) => updateField("production_output_id", event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.productionOrderItemId")}</span>
              <input
                style={sharedStyles.input}
                value={values.production_order_item_id}
                onChange={(event) =>
                  updateField("production_order_item_id", event.target.value)
                }
                disabled={isSubmitting}
              />
            </label>
          </div>

          {!hasQualityReference ? (
            <div style={styles.warning}>
              {t("missingReferenceWarning")}
            </div>
          ) : null}

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("rejectionJustificationSection")} ({common("labels.required")})</span>
            <textarea
              style={{ ...sharedStyles.textarea, minHeight: "120px" }}
              value={values.rejection_notes}
              onChange={(event) => updateField("rejection_notes", event.target.value)}
              disabled={isSubmitting}
              placeholder={t("placeholders.rejectionNotes")}
              required
            />
            {notesError ? <p style={styles.inlineError}>{notesError}</p> : null}
          </label>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.additionalNotes")}</span>
            <textarea
              style={sharedStyles.textarea}
              value={values.notes}
              onChange={(event) => updateField("notes", event.target.value)}
              disabled={isSubmitting}
            />
          </label>

          {error ? (
            <div style={sharedStyles.error} role="alert">
              {error}
            </div>
          ) : null}

          <div style={styles.actions}>
            <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
              {isSubmitting ? t("creating") : t("createButton")}
            </button>
            <Link href="/quality-rejections" style={sharedStyles.secondaryButton}>
              {common("actions.cancel")}
            </Link>
          </div>
        </form>
      </section>
    </PageFrame>
  );
}

function toCreateRequest(values: QualityRejectionFormValues): CreateQualityRejectionRequest {
  return {
    quality_check_id: optionalText(values.quality_check_id) ?? null,
    quality_defect_id: optionalText(values.quality_defect_id) ?? null,
    production_output_id: optionalText(values.production_output_id) ?? null,
    production_order_item_id: optionalText(values.production_order_item_id) ?? null,
    rejection_date: values.rejection_date,
    rejection_reason: values.rejection_reason,
    rejection_notes: values.rejection_notes.trim(),
    disposition: values.disposition,
    quantity_rejected: Number(values.quantity_rejected),
    unit: values.unit,
    notes: optionalText(values.notes) ?? null,
  };
}
