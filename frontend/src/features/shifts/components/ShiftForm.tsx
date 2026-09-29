"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import type { CSSProperties, FormEvent } from "react";
import { useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createShift } from "../api/shifts-api";
import type { CreateShiftRequest, ShiftStatus, ShiftType } from "../types";

type ShiftFormValues = {
  code: string;
  name: string;
  shift_type: ShiftType;
  start_time: string;
  end_time: string;
  status: ShiftStatus;
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
  notice: {
    background: "var(--warning-soft)",
    border: "1px solid color-mix(in srgb, var(--warning) 35%, var(--surface))",
    borderRadius: "6px",
    color: "var(--warning)",
    fontSize: "14px",
    padding: "10px 12px",
  },
};

const defaultValues: ShiftFormValues = {
  code: "",
  name: "",
  shift_type: "morning",
  start_time: "07:00",
  end_time: "15:00",
  status: "active",
  notes: "",
};

export function ShiftForm() {
  const t = useTranslations("production.shifts");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const router = useRouter();
  const [values, setValues] = useState<ShiftFormValues>(defaultValues);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);



  const spansMidnight = values.start_time !== "" &&
    values.end_time !== "" &&
    values.end_time <= values.start_time;

  function updateField<TField extends keyof ShiftFormValues>(
    field: TField,
    value: ShiftFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const createdShift = await createShift(toCreateRequest(values));
      setSuccessRedirect(`/shifts/${createdShift.id}`);
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
        onOk={() => router.replace(successRedirect)}
        okLabel={common("actions.ok")}
      />
    ) : null}
    <PageFrame
      section="Production"
      title={t("createTitle")}
      subtitle={t("createSubtitle")}
      action={
        <Link href="/shifts" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      <section style={styles.panel}>
        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={styles.formGrid}>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.code")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                value={values.code}
                onChange={(event) => updateField("code", event.target.value)}
                maxLength={64}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.name")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                value={values.name}
                onChange={(event) => updateField("name", event.target.value)}
                maxLength={255}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.type")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <select
                style={sharedStyles.input}
                value={values.shift_type}
                onChange={(event) => updateField("shift_type", event.target.value as ShiftType)}
                disabled={isSubmitting}
                required
              >
                <option value="morning">Morning</option>
                <option value="evening">Evening</option>
                <option value="night">Night</option>
                <option value="custom">Custom</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.startTime")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="time"
                value={values.start_time}
                onChange={(event) => updateField("start_time", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.endTime")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="time"
                value={values.end_time}
                onChange={(event) => updateField("end_time", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.status")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <select
                style={sharedStyles.input}
                value={values.status}
                onChange={(event) => updateField("status", event.target.value as ShiftStatus)}
                disabled={isSubmitting}
                required
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </label>
          </div>

          {spansMidnight ? (
            <div style={styles.notice}>
              {t("crossesMidnightFormNotice")}
            </div>
          ) : null}

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.notes")}</span>
            <textarea
              style={{ ...sharedStyles.textarea, minHeight: "110px" }}
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
            <button
              style={sharedStyles.button}
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? t("creating") : t("createButton")}
            </button>
            <Link href="/shifts" style={sharedStyles.secondaryButton}>
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

function toCreateRequest(values: ShiftFormValues): CreateShiftRequest {
  return {
    code: values.code,
    name: values.name,
    shift_type: values.shift_type,
    start_time: values.start_time,
    end_time: values.end_time,
    status: values.status,
    notes: optionalText(values.notes) ?? null,
  };
}
