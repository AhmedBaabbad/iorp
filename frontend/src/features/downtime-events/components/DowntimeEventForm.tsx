"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import type { CSSProperties, FormEvent } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getWorkCenters } from "@/features/work-centers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createDowntimeEvent } from "../api/downtime-events-api";
import type { CreateDowntimeEventRequest, DowntimeCategory } from "../types";
import {
  downtimeCategories,
  formatCategory,
  toIsoDatetime,
  toOptionalIsoDatetime,
} from "./downtime-events-utils";

type DowntimeEventFormValues = {
  work_center_id: string;
  shift_report_id: string;
  production_order_id: string;
  start_time: string;
  end_time: string;
  category: DowntimeCategory;
  reason_code: string;
  notes: string;
};

type WorkCenterOption = {
  id: string;
  code: string;
  name: string;
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

const defaultValues: DowntimeEventFormValues = {
  work_center_id: "",
  shift_report_id: "",
  production_order_id: "",
  start_time: "",
  end_time: "",
  category: "machine",
  reason_code: "",
  notes: "",
};

export function DowntimeEventForm() {
  const tEnums = useTranslations();
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const router = useRouter();
  const [values, setValues] = useState<DowntimeEventFormValues>(defaultValues);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [isLoadingWorkCenters, setIsLoadingWorkCenters] = useState(true);
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
  }, []);

  function updateField<TField extends keyof DowntimeEventFormValues>(
    field: TField,
    value: DowntimeEventFormValues[TField],
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
      const createdEvent = await createDowntimeEvent(toCreateRequest(values));
      router.replace(`/downtime-events/${createdEvent.id}`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <PageFrame
      section="Production"
      title="Record downtime event"
      subtitle="Record a stoppage. Status and duration are calculated automatically."
      action={
        <Link href="/downtime-events" style={sharedStyles.secondaryButton}>
          Back to Downtime Events
        </Link>
      }
    >
      <section style={styles.panel}>
        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={sharedStyles.state}>
            Duration is auto-calculated. Status will be set to Open if no end time is provided.
          </div>

          <div style={styles.formGrid}>
            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                Work Center
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <select
                style={sharedStyles.input}
                value={values.work_center_id}
                onChange={(event) => updateField("work_center_id", event.target.value)}
                disabled={isSubmitting || isLoadingWorkCenters || workCenters.length === 0}
                required
              >
                {isLoadingWorkCenters ? <option value="">{messages("loading.fetching")}</option> : null}
                {!isLoadingWorkCenters && workCenters.length === 0 ? (
                  <option value="">No work centers available</option>
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
                Start Time
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="datetime-local"
                value={values.start_time}
                onChange={(event) => updateField("start_time", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>End Time</span>
              <input
                style={sharedStyles.input}
                type="datetime-local"
                value={values.end_time}
                onChange={(event) => updateField("end_time", event.target.value)}
                disabled={isSubmitting}
              />
              <span style={sharedStyles.meta}>
                Leave empty to create an open downtime event (still ongoing)
              </span>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                Category
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <select
                style={sharedStyles.input}
                value={values.category}
                onChange={(event) =>
                  updateField("category", event.target.value as DowntimeCategory)
                }
                disabled={isSubmitting}
                required
              >
                {downtimeCategories.map((category) => (
                  <option key={category} value={category}>
                    {formatCategory(category, tEnums)}
                  </option>
                ))}
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Reason Code</span>
              <input
                style={sharedStyles.input}
                value={values.reason_code}
                placeholder="Describe the specific reason..."
                onChange={(event) => updateField("reason_code", event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Shift Report ID</span>
              <input
                style={sharedStyles.input}
                value={values.shift_report_id}
                onChange={(event) => updateField("shift_report_id", event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Production Order ID</span>
              <input
                style={sharedStyles.input}
                value={values.production_order_id}
                onChange={(event) => updateField("production_order_id", event.target.value)}
                disabled={isSubmitting}
              />
            </label>
          </div>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>Notes</span>
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

          {error ? (
            <div style={sharedStyles.error} role="alert">
              {error}
            </div>
          ) : null}

          <div style={styles.actions}>
            <button
              style={sharedStyles.button}
              type="submit"
              disabled={isSubmitting || isLoadingWorkCenters || workCenters.length === 0}
            >
              {isSubmitting ? messages("loading.saving") : common("actions.create")}
            </button>
            <Link href="/downtime-events" style={sharedStyles.secondaryButton}>
              {common("actions.cancel")}
            </Link>
            <span style={styles.requiredNote}>* {common("labels.required")}</span>
          </div>
        </form>
      </section>
    </PageFrame>
  );
}

function toCreateRequest(values: DowntimeEventFormValues): CreateDowntimeEventRequest {
  return {
    work_center_id: values.work_center_id,
    shift_report_id: optionalText(values.shift_report_id) ?? null,
    production_order_id: optionalText(values.production_order_id) ?? null,
    start_time: toIsoDatetime(values.start_time),
    end_time: toOptionalIsoDatetime(values.end_time),
    category: values.category,
    reason_code: optionalText(values.reason_code) ?? null,
    notes: optionalText(values.notes) ?? null,
  };
}
