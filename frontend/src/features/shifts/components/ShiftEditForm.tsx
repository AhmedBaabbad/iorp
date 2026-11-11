"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import type { CSSProperties } from "react";
import { useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { updateShift } from "../api/shifts-api";
import type { ShiftData, ShiftStatus, ShiftType, UpdateShiftRequest } from "../types";
import { formatShiftStatus, formatShiftType } from "./shift-utils";

type EditFormValues = {
  code: string;
  name: string;
  shift_type: ShiftType;
  start_time: string;
  end_time: string;
  status: ShiftStatus;
  notes: string;
};


const SHIFT_TYPES: ShiftType[] = ["morning", "evening", "night", "custom"];
const SHIFT_STATUSES: ShiftStatus[] = ["active", "inactive"];

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
  notice: {
    background: "var(--warning-soft)",
    border: "1px solid color-mix(in srgb, var(--warning) 35%, var(--surface))",
    borderRadius: "6px",
    color: "var(--warning)",
    fontSize: "14px",
    padding: "10px 12px",
  },
};

type Props = { shift: ShiftData };

export function ShiftEditForm({ shift }: Props) {
  const router = useRouter();
  const t = useTranslations("production.shifts");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const tEnums = useTranslations();
  const [values, setValues] = useState<EditFormValues>(() => toFormValues(shift));
  const [nameManual, setNameManual] = useState(() => shift.shift_type === "custom" || shift.name !== t(`defaultNames.${shift.shift_type}`));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);



  const spansMidnight =
    values.start_time !== "" &&
    values.end_time !== "" &&
    values.end_time <= values.start_time;

  function updateField<TField extends keyof EditFormValues>(
    field: TField,
    value: EditFormValues[TField],
  ) {
    if (field === "name") setNameManual(true);
    setValues(current => ({ ...current, [field]: value,
      ...(field === "shift_type" && !nameManual
        ? { name: value === "custom" ? "" : t(`defaultNames.${value as Exclude<ShiftType, "custom">}`) } : {}),
    }));
  }

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await updateShift(shift.id, toUpdateRequest(values));
      setSuccessRedirect(`/shifts/${shift.id}`);
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
        title={`${t("editTitle")} — ${shift.code}`}
        subtitle={t("editSubtitle")}
        action={
          <Link href={`/shifts/${shift.id}`} style={sharedStyles.secondaryButton}>
            {t("backToDetail")}
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
                  onChange={(e) => updateField("code", e.target.value)}
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
                  onChange={(e) => updateField("name", e.target.value)}
                  maxLength={255}
                  disabled={isSubmitting}
                  required
                />
              <small style={{ color: "var(--text-muted)" }}>{t("nameHint")}</small>
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.type")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <select
                  style={sharedStyles.input}
                  value={values.shift_type}
                  onChange={(e) => updateField("shift_type", e.target.value as ShiftType)}
                  disabled={isSubmitting}
                  required
                >
                  {SHIFT_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {formatShiftType(type, tEnums)}
                    </option>
                  ))}
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
                  onChange={(e) => updateField("start_time", e.target.value)}
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
                  onChange={(e) => updateField("end_time", e.target.value)}
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
                  onChange={(e) => updateField("status", e.target.value as ShiftStatus)}
                  disabled={isSubmitting}
                  required
                >
                  {SHIFT_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {formatShiftStatus(s, tEnums)}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {spansMidnight ? (
              <div style={styles.notice}>{t("crossesMidnightFormNotice")}</div>
            ) : null}

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
              <button
                style={sharedStyles.button}
                type="submit"
                disabled={isSubmitting}
              >
                {isSubmitting ? messages("loading.saving") : t("updateButton")}
              </button>
              <Link href={`/shifts/${shift.id}`} style={sharedStyles.secondaryButton}>
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

function toFormValues(shift: ShiftData): EditFormValues {
  return {
    code: shift.code,
    name: shift.name,
    shift_type: shift.shift_type,
    start_time: shift.start_time,
    end_time: shift.end_time,
    status: shift.status,
    notes: shift.notes ?? "",
  };
}

function toUpdateRequest(values: EditFormValues): UpdateShiftRequest {
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
