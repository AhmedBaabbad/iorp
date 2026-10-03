"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties, FormEvent } from "react";
import { useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createNcrReport } from "../api/ncr-reports-api";
import type { CreateNcrReportRequest, NCRReportType, NCRSourceType } from "../types";

type NcrReportFormValues = {
  report_date: string;
  source_type: NCRSourceType;
  report_type: NCRReportType;
  title: string;
  reference_code: string;
  quality_check_id: string;
  quality_rejection_id: string;
  description: string;
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
};

const defaultValues: NcrReportFormValues = {
  report_date: new Date().toISOString().slice(0, 10),
  source_type: "internal_production",
  report_type: "product_non_conformance",
  title: "",
  reference_code: "",
  quality_check_id: "",
  quality_rejection_id: "",
  description: "",
};

export function NcrReportForm() {
  const router = useRouter();
  const t = useTranslations("ncr.ncrReports");
  const enumT = useTranslations("enums");
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const [values, setValues] = useState<NcrReportFormValues>(defaultValues);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [descriptionError, setDescriptionError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateField<TField extends keyof NcrReportFormValues>(
    field: TField,
    value: NcrReportFormValues[TField],
  ) {
    setValues((current) => ({ ...current, [field]: value }));

    if (field === "title") {
      setTitleError(null);
    }

    if (field === "description") {
      setDescriptionError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setTitleError(null);
    setDescriptionError(null);

    if (!values.title.trim()) {
      setTitleError(messages("validation.titleRequired"));
      return;
    }

    if (!values.description.trim()) {
      setDescriptionError(messages("validation.descriptionRequired"));
      return;
    }

    setIsSubmitting(true);

    try {
      const createdReport = await createNcrReport(toCreateRequest(values));
      router.replace(`/non-conformance-reports/${createdReport.id}`);
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
        <Link href="/non-conformance-reports" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      <section style={styles.panel}>
        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={sharedStyles.state}>
            {t("fields.reportNumber")}: {t("reportNumberAuto")}
          </div>

          <div style={styles.formGrid}>
            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.reportDate")} *</span>
              <input
                style={sharedStyles.input}
                type="date"
                value={values.report_date}
                onChange={(event) => updateField("report_date", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.sourceType")} *</span>
              <select
                style={sharedStyles.input}
                value={values.source_type}
                onChange={(event) =>
                  updateField("source_type", event.target.value as NCRSourceType)
                }
                disabled={isSubmitting}
                required
              >
                <option value="internal_production">{enumT("ncrReport.sourceType.internal_production")}</option>
                <option value="incoming_material">{enumT("ncrReport.sourceType.incoming_material")}</option>
                <option value="supplier">{enumT("ncrReport.sourceType.supplier")}</option>
                <option value="warehouse">{enumT("ncrReport.sourceType.warehouse")}</option>
                <option value="customer_return">{enumT("ncrReport.sourceType.customer_return")}</option>
                <option value="other">{enumT("ncrReport.sourceType.other")}</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.reportType")} *</span>
              <select
                style={sharedStyles.input}
                value={values.report_type}
                onChange={(event) =>
                  updateField("report_type", event.target.value as NCRReportType)
                }
                disabled={isSubmitting}
                required
              >
                <option value="material_non_conformance">{enumT("ncrReport.reportType.material_non_conformance")}</option>
                <option value="product_non_conformance">{enumT("ncrReport.reportType.product_non_conformance")}</option>
                <option value="process_non_conformance">{enumT("ncrReport.reportType.process_non_conformance")}</option>
                <option value="packaging_non_conformance">{enumT("ncrReport.reportType.packaging_non_conformance")}</option>
                <option value="documentation_non_conformance">{enumT("ncrReport.reportType.documentation_non_conformance")}</option>
                <option value="other">{enumT("ncrReport.reportType.other")}</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.title")} *</span>
              <input
                style={sharedStyles.input}
                value={values.title}
                onChange={(event) => updateField("title", event.target.value)}
                disabled={isSubmitting}
                required
              />
              {titleError ? <p style={styles.inlineError}>{titleError}</p> : null}
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.referenceCode")}</span>
              <input
                style={sharedStyles.input}
                value={values.reference_code}
                onChange={(event) => updateField("reference_code", event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.qualityCheck")}</span>
              <input
                style={sharedStyles.input}
                value={values.quality_check_id}
                onChange={(event) => updateField("quality_check_id", event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.qualityRejection")}</span>
              <input
                style={sharedStyles.input}
                value={values.quality_rejection_id}
                onChange={(event) => updateField("quality_rejection_id", event.target.value)}
                disabled={isSubmitting}
              />
            </label>
          </div>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.description")} *</span>
            <textarea
              style={{ ...sharedStyles.textarea, minHeight: "120px" }}
              value={values.description}
              onChange={(event) => updateField("description", event.target.value)}
              disabled={isSubmitting}
              required
            />
            {descriptionError ? <p style={styles.inlineError}>{descriptionError}</p> : null}
          </label>

          {error ? (
            <div style={sharedStyles.error} role="alert">
              {error}
            </div>
          ) : null}

          <div style={styles.actions}>
            <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
              {isSubmitting ? `${common("actions.create")}...` : t("createButton")}
            </button>
            <Link href="/non-conformance-reports" style={sharedStyles.secondaryButton}>
              {common("actions.cancel")}
            </Link>
          </div>
        </form>
      </section>
    </PageFrame>
  );
}

function toCreateRequest(values: NcrReportFormValues): CreateNcrReportRequest {
  return {
    report_date: values.report_date,
    source_type: values.source_type,
    report_type: values.report_type,
    title: values.title.trim(),
    description: values.description.trim(),
    reference_code: optionalText(values.reference_code) ?? null,
    quality_check_id: optionalText(values.quality_check_id) ?? null,
    quality_rejection_id: optionalText(values.quality_rejection_id) ?? null,
  };
}
