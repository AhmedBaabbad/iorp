"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { updateWorkCenter } from "../api/work-centers-api";
import type { UpdateWorkCenterRequest, WorkCenterData, WorkCenterStatus, WorkCenterType } from "../types";

type EditFormValues = {
  name: string;
  center_type: WorkCenterType;
  status: WorkCenterStatus;
  location: string;
  commissioned_date: string;
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
  codeDisplay: {
    background: "var(--surface-muted)",
    border: "1px solid var(--border)",
    borderRadius: "6px",
    color: "var(--text-muted)",
    fontFamily: "monospace",
    fontSize: "15px",
    fontWeight: 700,
    padding: "10px 14px",
  },
  actions: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: "12px",
    alignItems: "center",
  },
  required: {
    color: "var(--danger)",
    marginLeft: "2px",
  },
  requiredNote: {
    color: "var(--text-muted)",
    fontSize: "13px",
    marginLeft: "auto",
  },
};

const CENTER_TYPES: WorkCenterType[] = [
  "extrusion",
  "rewinding",
  "packing",
  "quality_station",
  "generic",
];

const CENTER_STATUSES: WorkCenterStatus[] = ["active", "inactive", "under_maintenance"];

type Props = { workCenter: WorkCenterData };

export function WorkCenterEditForm({ workCenter }: Props) {
  const router = useRouter();
  const t = useTranslations("production.workCenters");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const tEnums = useTranslations();
  const [values, setValues] = useState<EditFormValues>(() => toFormValues(workCenter));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);

  function updateField<TField extends keyof EditFormValues>(
    field: TField,
    value: EditFormValues[TField],
  ) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await updateWorkCenter(workCenter.id, toUpdateRequest(values));
      setSuccessRedirect(`/work-centers/${workCenter.id}`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      {successRedirect ? (
        <SuccessModal
          message={t("updateSuccess")}
          okLabel={common("actions.ok")}
          onOk={() => router.replace(successRedirect)}
        />
      ) : null}
      <PageFrame
        section="Production"
        title={`${t("editTitle")} — ${workCenter.code}`}
        subtitle={t("editSubtitle")}
        action={
          <Link href={`/work-centers/${workCenter.id}`} style={sharedStyles.secondaryButton}>
            {t("backToDetail")}
          </Link>
        }
      >
        <section style={styles.panel}>
          <form style={styles.form} onSubmit={handleSubmit}>
            <div style={styles.formGrid}>
              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.centerCode")}</span>
                <div style={styles.codeDisplay}>{workCenter.code}</div>
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.name")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <input
                  style={sharedStyles.input}
                  value={values.name}
                  onChange={(e) => updateField("name", e.target.value)}
                  maxLength={255}
                  disabled={isSubmitting}
                  required
                />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.centerType")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <select
                  style={sharedStyles.input}
                  value={values.center_type}
                  onChange={(e) => updateField("center_type", e.target.value as WorkCenterType)}
                  disabled={isSubmitting}
                  required
                >
                  {CENTER_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {getEnumLabel("workCenter", "centerType", type, tEnums)}
                    </option>
                  ))}
                </select>
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.status")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <select
                  style={sharedStyles.input}
                  value={values.status}
                  onChange={(e) => updateField("status", e.target.value as WorkCenterStatus)}
                  disabled={isSubmitting}
                  required
                >
                  {CENTER_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {getEnumLabel("workCenter", "status", s, tEnums)}
                    </option>
                  ))}
                </select>
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.location")}</span>
                <input
                  style={sharedStyles.input}
                  value={values.location}
                  onChange={(e) => updateField("location", e.target.value)}
                  maxLength={255}
                  disabled={isSubmitting}
                />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.commissionedDate")}</span>
                <input
                  style={sharedStyles.input}
                  type="date"
                  value={values.commissioned_date}
                  onChange={(e) => updateField("commissioned_date", e.target.value)}
                  disabled={isSubmitting}
                />
              </label>
            </div>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.notes")}</span>
              <textarea
                style={{ ...sharedStyles.textarea, minHeight: "110px" }}
                value={values.notes}
                onChange={(e) => updateField("notes", e.target.value)}
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
                {isSubmitting ? messages("loading.saving") : t("updateButton")}
              </button>
              <Link href={`/work-centers/${workCenter.id}`} style={sharedStyles.secondaryButton}>
                {common("actions.cancel")}
              </Link>
              <span style={styles.requiredNote}>* {common("labels.required")}</span>
            </div>
          </form>
        </section>
      </PageFrame>
    </>
  );
}

function toFormValues(wc: WorkCenterData): EditFormValues {
  return {
    name: wc.name,
    center_type: wc.center_type,
    status: wc.status,
    location: wc.location ?? "",
    commissioned_date: wc.commissioned_date ?? "",
    notes: wc.notes ?? "",
  };
}

function toUpdateRequest(values: EditFormValues): UpdateWorkCenterRequest {
  return {
    name: values.name,
    center_type: values.center_type,
    status: values.status,
    location: optionalText(values.location) ?? null,
    commissioned_date: optionalText(values.commissioned_date) ?? null,
    notes: optionalText(values.notes) ?? null,
  };
}
