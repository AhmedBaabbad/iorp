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
import { createWorkCenter } from "../api/work-centers-api";
import type { CreateWorkCenterRequest, WorkCenterStatus, WorkCenterType } from "../types";

type WorkCenterFormValues = {
  name: string;
  center_type: WorkCenterType;
  status: WorkCenterStatus;
  location: string;
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

const defaultValues: WorkCenterFormValues = {
  name: "",
  center_type: "generic",
  status: "active",
  location: "",
  notes: "",
};

export function WorkCenterForm() {
  const router = useRouter();
  const t = useTranslations("production.workCenters");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const tEnums = useTranslations();
  const [values, setValues] = useState<WorkCenterFormValues>(defaultValues);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);

  function updateField<TField extends keyof WorkCenterFormValues>(
    field: TField,
    value: WorkCenterFormValues[TField],
  ) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const created = await createWorkCenter(toCreateRequest(values));
      setSuccessRedirect(`/work-centers/${created.id}`);
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
          message={t("createSuccess")}
          okLabel={common("actions.ok")}
          onOk={() => router.replace(successRedirect)}
        />
      ) : null}
      <PageFrame
        section="Production"
        title={t("createTitle")}
        subtitle={t("createSubtitle")}
        action={
          <Link href="/work-centers" style={sharedStyles.secondaryButton}>
            {t("backToList")}
          </Link>
        }
      >
        <section style={styles.panel}>
          <form style={styles.form} onSubmit={handleSubmit}>
            <div style={styles.formGrid}>
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
                {isSubmitting ? messages("loading.saving") : t("createButton")}
              </button>
              <Link href="/work-centers" style={sharedStyles.secondaryButton}>
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

function toCreateRequest(values: WorkCenterFormValues): CreateWorkCenterRequest {
  return {
    name: values.name,
    center_type: values.center_type,
    status: values.status,
    location: optionalText(values.location) ?? null,
    notes: optionalText(values.notes) ?? null,
  };
}
