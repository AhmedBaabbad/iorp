"use client";

import type { CSSProperties, FormEvent } from "react";
import { useState } from "react";
import { useTranslations } from "next-intl";

import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createFollowUp } from "../api/action-follow-ups-api";
import type {
  ActionFollowUpStatus,
  CreateActionFollowUpRequest,
} from "../types";

type ActionFollowUpFormProps = {
  correctiveActionId: string;
  onCreated: () => Promise<void>;
  onCancel: () => void;
};

type ActionFollowUpFormValues = {
  follow_up_date: string;
  status: ActionFollowUpStatus;
  progress_note: string;
  next_step: string;
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

function createDefaultValues(): ActionFollowUpFormValues {
  return {
    follow_up_date: new Date().toISOString().slice(0, 10),
    status: "on_track",
    progress_note: "",
    next_step: "",
  };
}

export function ActionFollowUpForm({
  correctiveActionId,
  onCreated,
  onCancel,
}: ActionFollowUpFormProps) {
  const t = useTranslations("capa.correctiveActions.followUps");
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const [values, setValues] = useState<ActionFollowUpFormValues>(createDefaultValues);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [dateError, setDateError] = useState<string | null>(null);
  const [progressError, setProgressError] = useState<string | null>(null);

  function updateField<TField extends keyof ActionFollowUpFormValues>(
    field: TField,
    value: ActionFollowUpFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));

    if (field === "follow_up_date") {
      setDateError(null);
    }

    if (field === "progress_note") {
      setProgressError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setDateError(null);
    setProgressError(null);

    if (!values.follow_up_date) {
      setDateError(messages("validation.dateRequired"));
      return;
    }

    if (!values.progress_note.trim()) {
      setProgressError(messages("validation.progressRequired"));
      return;
    }

    setIsSubmitting(true);

    try {
      await createFollowUp(correctiveActionId, toCreateRequest(values));
      setValues(createDefaultValues());
      await onCreated();
      onCancel();
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
            {t("fields.followUpDate")} <span aria-hidden="true" style={{ color: "var(--danger)" }}>*</span>
          </span>
          <input
            style={sharedStyles.input}
            type="date"
            value={values.follow_up_date}
            onChange={(event) => updateField("follow_up_date", event.target.value)}
            disabled={isSubmitting}
            required
          />
          {dateError ? <p style={styles.inlineError}>{dateError}</p> : null}
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>
            {t("fields.status")} <span aria-hidden="true" style={{ color: "var(--danger)" }}>*</span>
          </span>
          <select
            style={sharedStyles.input}
            value={values.status}
            onChange={(event) =>
              updateField("status", event.target.value as ActionFollowUpStatus)
            }
            disabled={isSubmitting}
            required
          >
            <option value="on_track">On Track</option>
            <option value="delayed">Delayed</option>
            <option value="blocked">Blocked (Needs Attention)</option>
            <option value="completed">Completed</option>
          </select>
        </label>
      </div>

      <label style={sharedStyles.field}>
        <span style={sharedStyles.label}>
          {t("fields.progressNote")} ({common("labels.required")})
        </span>
        <textarea
          style={{ ...sharedStyles.textarea, minHeight: "110px" }}
          value={values.progress_note}
          onChange={(event) => updateField("progress_note", event.target.value)}
          disabled={isSubmitting}
          placeholder={t("progressPlaceholder")}
          required
        />
        {progressError ? <p style={styles.inlineError}>{progressError}</p> : null}
      </label>

      <label style={sharedStyles.field}>
        <span style={sharedStyles.label}>{t("fields.nextStep")}</span>
        <textarea
          style={sharedStyles.textarea}
          value={values.next_step}
          onChange={(event) => updateField("next_step", event.target.value)}
          disabled={isSubmitting}
          placeholder={t("nextStepPlaceholder")}
        />
      </label>

      {formError ? (
        <div style={sharedStyles.error} role="alert">
          {formError}
        </div>
      ) : null}

      <div style={styles.actions}>
        <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
          {isSubmitting ? t("saving") : t("addButton")}
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

function toCreateRequest(values: ActionFollowUpFormValues): CreateActionFollowUpRequest {
  return {
    follow_up_date: values.follow_up_date,
    status: values.status,
    progress_note: values.progress_note.trim(),
    next_step: optionalText(values.next_step) ?? null,
  };
}
