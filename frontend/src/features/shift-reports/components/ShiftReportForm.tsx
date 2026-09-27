"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import type { CSSProperties, FormEvent } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getShifts } from "@/features/shifts";
import { getWorkCenters } from "@/features/work-centers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createShiftReport } from "../api/shift-reports-api";
import type { CreateShiftReportRequest } from "../types";
import { formatShiftType } from "./shift-report-utils";

type ShiftReportFormValues = {
  work_center_id: string;
  shift_definition_id: string;
  production_order_id: string;
  report_date: string;
  shift_started_at: string;
  shift_ended_at: string;
  summary: string;
  notes: string;
};

type WorkCenterOption = {
  id: string;
  code: string;
  name: string;
};

type ShiftOption = {
  id: string;
  code: string;
  name: string;
  shift_type: string;
};

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "#ffffff",
    border: "1px solid #d9dee7",
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
    color: "#be123c",
    marginLeft: "2px",
  },
  requiredNote: {
    color: "#52606d",
    fontSize: "13px",
    marginLeft: "auto",
  },
};

const defaultValues: ShiftReportFormValues = {
  work_center_id: "",
  shift_definition_id: "",
  production_order_id: "",
  report_date: "",
  shift_started_at: "",
  shift_ended_at: "",
  summary: "",
  notes: "",
};

export function ShiftReportForm() {
  const t = useTranslations("production.shiftReports");
  const tEnums = useTranslations();
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const router = useRouter();
  const [values, setValues] = useState<ShiftReportFormValues>(defaultValues);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [shifts, setShifts] = useState<ShiftOption[]>([]);
  const [isLoadingWorkCenters, setIsLoadingWorkCenters] = useState(true);
  const [isLoadingShifts, setIsLoadingShifts] = useState(false);
  const [referenceError, setReferenceError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadWorkCenters() {
      try {
        setIsLoadingWorkCenters(true);
        setReferenceError(null);
        const response = await getWorkCenters();

        if (isMounted) {
          setWorkCenters(response);
          setValues((current) => ({
            ...current,
            work_center_id: current.work_center_id || response[0]?.id || "",
          }));
        }
      } catch (caughtError) {
        if (isMounted) {
          setReferenceError(getApiErrorMessage(caughtError, messages));
        }
      } finally {
        if (isMounted) {
          setIsLoadingWorkCenters(false);
        }
      }
    }

    void loadWorkCenters();

    return () => {
      isMounted = false;
    };
  }, [t, messages]);

  useEffect(() => {
    let isMounted = true;

    async function loadShiftsForWorkCenter() {
      if (!values.work_center_id) {
        setShifts([]);
        setValues((current) => ({ ...current, shift_definition_id: "" }));
        return;
      }

      try {
        setIsLoadingShifts(true);
        setReferenceError(null);
        const response = await getShifts();

        if (isMounted) {
          setShifts(response);
          setValues((current) => ({
            ...current,
            shift_definition_id: response.some((shift) => shift.id === current.shift_definition_id)
              ? current.shift_definition_id
              : response[0]?.id || "",
          }));
        }
      } catch (caughtError) {
        if (isMounted) {
          setReferenceError(getApiErrorMessage(caughtError, messages));
        }
      } finally {
        if (isMounted) {
          setIsLoadingShifts(false);
        }
      }
    }

    void loadShiftsForWorkCenter();

    return () => {
      isMounted = false;
    };
  }, [values.work_center_id, t, messages]);

  function updateField<TField extends keyof ShiftReportFormValues>(
    field: TField,
    value: ShiftReportFormValues[TField],
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
      const createdReport = await createShiftReport(toCreateRequest(values));
      router.replace(`/shift-reports/${createdReport.id}`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <PageFrame
      section="Production"
      title={t("createTitle")}
      subtitle={t("createSubtitle")}
      action={
        <Link href="/shift-reports" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      <section style={styles.panel}>
        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={sharedStyles.state}>
            {t("statusDraftNotice")}
          </div>

          <div style={styles.formGrid}>
            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.workCenter")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <select
                style={sharedStyles.input}
                value={values.work_center_id}
                onChange={(event) => updateField("work_center_id", event.target.value)}
                disabled={isSubmitting || isLoadingWorkCenters || workCenters.length === 0}
                required
              >
                {isLoadingWorkCenters ? <option value="">{t("loadingWorkCenters")}</option> : null}
                {!isLoadingWorkCenters && workCenters.length === 0 ? (
                  <option value="">{t("noWorkCentersAvailable")}</option>
                ) : null}
                {workCenters.map((workCenter) => (
                  <option key={workCenter.id} value={workCenter.id}>
                    {workCenter.code} - {workCenter.name}
                  </option>
                ))}
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.shift")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <select
                style={sharedStyles.input}
                value={values.shift_definition_id}
                onChange={(event) => updateField("shift_definition_id", event.target.value)}
                disabled={isSubmitting || isLoadingShifts || shifts.length === 0}
                required
              >
                {isLoadingShifts ? <option value="">{t("loadingShifts")}</option> : null}
                {!isLoadingShifts && shifts.length === 0 ? (
                  <option value="">{t("noShiftsAvailable")}</option>
                ) : null}
                {shifts.map((shift) => (
                  <option key={shift.id} value={shift.id}>
                    {shift.code} - {shift.name} ({formatShiftType(shift.shift_type, tEnums)})
                  </option>
                ))}
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.reportDate")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
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
              <span style={sharedStyles.label}>{t("fields.productionOrderId")}</span>
              <input
                style={sharedStyles.input}
                value={values.production_order_id}
                onChange={(event) => updateField("production_order_id", event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.shiftStartTime")} ({common("labels.optional")})</span>
              <input
                style={sharedStyles.input}
                type="datetime-local"
                value={values.shift_started_at}
                onChange={(event) => updateField("shift_started_at", event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.shiftEndTime")} ({common("labels.optional")})</span>
              <input
                style={sharedStyles.input}
                type="datetime-local"
                value={values.shift_ended_at}
                onChange={(event) => updateField("shift_ended_at", event.target.value)}
                disabled={isSubmitting}
              />
            </label>
          </div>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>
              {t("fields.summary")}
              <span style={styles.required} aria-hidden="true"> *</span>
            </span>
            <textarea
              style={{ ...sharedStyles.textarea, minHeight: "120px" }}
              value={values.summary}
              onChange={(event) => updateField("summary", event.target.value)}
              disabled={isSubmitting}
              required
            />
          </label>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.notes")}</span>
            <textarea
              style={{ ...sharedStyles.textarea, minHeight: "110px" }}
              value={values.notes}
              onChange={(event) => updateField("notes", event.target.value)}
              disabled={isSubmitting}
            />
          </label>

          {referenceError ? (
            <div style={sharedStyles.error} role="alert">
              {referenceError}
            </div>
          ) : null}

          {!isLoadingWorkCenters && !referenceError && workCenters.length === 0 ? (
            <div style={sharedStyles.state}>
              {t("noWorkCentersFound")}
            </div>
          ) : null}

          {error ? (
            <div style={sharedStyles.error} role="alert">
              {error}
            </div>
          ) : null}

          <div style={styles.actions}>
            <button
              style={sharedStyles.button}
              type="submit"
              disabled={
                isSubmitting ||
                isLoadingWorkCenters ||
                isLoadingShifts ||
                workCenters.length === 0 ||
                shifts.length === 0
              }
            >
              {isSubmitting ? t("creating") : t("createButton")}
            </button>
            <Link href="/shift-reports" style={sharedStyles.secondaryButton}>
              {common("actions.cancel")}
            </Link>
            <span style={styles.requiredNote}>* {common("labels.required")}</span>
          </div>
        </form>
      </section>
    </PageFrame>
  );
}

function toCreateRequest(values: ShiftReportFormValues): CreateShiftReportRequest {
  return {
    work_center_id: values.work_center_id,
    shift_definition_id: values.shift_definition_id,
    production_order_id: optionalText(values.production_order_id) ?? null,
    report_date: values.report_date,
    shift_started_at: toOptionalIsoDatetime(values.shift_started_at),
    shift_ended_at: toOptionalIsoDatetime(values.shift_ended_at),
    summary: values.summary,
    notes: optionalText(values.notes) ?? null,
  };
}

function toOptionalIsoDatetime(value: string) {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return null;
  }

  return new Date(trimmed).toISOString();
}
