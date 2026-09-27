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
import { createCorrectiveAction } from "../api/corrective-actions-api";
import type {
  CorrectiveActionPriority,
  CorrectiveActionSourceType,
  CorrectiveActionType,
  CreateCorrectiveActionRequest,
} from "../types";

type CorrectiveActionFormValues = {
  title: string;
  description: string;
  action_type: CorrectiveActionType;
  priority: CorrectiveActionPriority;
  due_date: string;
  owner_user_id: string;
  source_type: "" | CorrectiveActionSourceType;
  source_id: string;
  notes: string;
};

const defaultValues: CorrectiveActionFormValues = {
  title: "",
  description: "",
  action_type: "corrective",
  priority: "normal",
  due_date: "",
  owner_user_id: "",
  source_type: "",
  source_id: "",
  notes: "",
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
  inlineError: {
    color: "#be123c",
    fontSize: "13px",
    margin: 0,
  },
};

export function CorrectiveActionForm() {
  const router = useRouter();
  const t = useTranslations("capa.correctiveActions");
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const [values, setValues] = useState<CorrectiveActionFormValues>(defaultValues);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [descriptionError, setDescriptionError] = useState<string | null>(null);
  const [dueDateError, setDueDateError] = useState<string | null>(null);
  const [ownerError, setOwnerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateField<TField extends keyof CorrectiveActionFormValues>(
    field: TField,
    value: CorrectiveActionFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
      ...(field === "source_type" && value === "manual" ? { source_id: "" } : {}),
    }));

    if (field === "title") {
      setTitleError(null);
    }

    if (field === "description") {
      setDescriptionError(null);
    }

    if (field === "due_date") {
      setDueDateError(null);
    }

    if (field === "owner_user_id") {
      setOwnerError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setTitleError(null);
    setDescriptionError(null);
    setDueDateError(null);
    setOwnerError(null);

    if (!values.title.trim()) {
      setTitleError(messages("validation.titleRequired"));
      return;
    }

    if (!values.description.trim()) {
      setDescriptionError(messages("validation.descriptionRequired"));
      return;
    }

    if (!values.due_date) {
      setDueDateError(messages("validation.dueDateRequired"));
      return;
    }

    if (!values.owner_user_id.trim()) {
      setOwnerError(messages("validation.ownerRequired"));
      return;
    }

    setIsSubmitting(true);

    try {
      const createdAction = await createCorrectiveAction(toCreateRequest(values));
      router.replace(`/corrective-actions/${createdAction.id}`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <PageFrame
      section="CAPA"
      title={t("createTitle")}
      subtitle={t("createSubtitle")}
      action={
        <Link href="/corrective-actions" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      <section style={styles.panel}>
        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={sharedStyles.state}>
            {t("fields.actionCode")}: {t("actionCodeAuto")}
          </div>

          <div style={styles.formGrid}>
            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.actionType")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <select
                style={sharedStyles.input}
                value={values.action_type}
                onChange={(event) =>
                  updateField("action_type", event.target.value as CorrectiveActionType)
                }
                disabled={isSubmitting}
                required
              >
                <option value="corrective">Corrective (Fix after problem)</option>
                <option value="preventive">Preventive (Prevent recurrence)</option>
                <option value="improvement">Improvement (Process improvement)</option>
                <option value="containment">Containment (Immediate containment)</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.priority")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <select
                style={sharedStyles.input}
                value={values.priority}
                onChange={(event) =>
                  updateField("priority", event.target.value as CorrectiveActionPriority)
                }
                disabled={isSubmitting}
                required
              >
                <option value="urgent">Urgent</option>
                <option value="high">High</option>
                <option value="normal">Normal</option>
                <option value="low">Low</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.dueDate")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="date"
                value={values.due_date}
                onChange={(event) => updateField("due_date", event.target.value)}
                disabled={isSubmitting}
                required
              />
              {dueDateError ? <p style={styles.inlineError}>{dueDateError}</p> : null}
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.owner")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                value={values.owner_user_id}
                onChange={(event) => updateField("owner_user_id", event.target.value)}
                disabled={isSubmitting}
                required
              />
              {ownerError ? <p style={styles.inlineError}>{ownerError}</p> : null}
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.sourceType")}</span>
              <select
                style={sharedStyles.input}
                value={values.source_type}
                onChange={(event) =>
                  updateField("source_type", event.target.value as "" | CorrectiveActionSourceType)
                }
                disabled={isSubmitting}
              >
                <option value="">No source selected</option>
                <option value="quality_rejection">Quality Rejection</option>
                <option value="ncr_report">NCR Report</option>
                <option value="quality_defect">Quality Defect</option>
                <option value="ncr_item">NCR Item</option>
                <option value="manual">Manual (No source)</option>
              </select>
            </label>

            {values.source_type && values.source_type !== "manual" ? (
              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.sourceId")}</span>
                <input
                  style={sharedStyles.input}
                  value={values.source_id}
                  onChange={(event) => updateField("source_id", event.target.value)}
                  disabled={isSubmitting}
                />
              </label>
            ) : null}
          </div>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>
              {t("fields.title")}
              <span style={styles.required} aria-hidden="true"> *</span>
            </span>
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
            <span style={sharedStyles.label}>
              {t("fields.description")}
              <span style={styles.required} aria-hidden="true"> *</span>
            </span>
            <textarea
              style={{ ...sharedStyles.textarea, minHeight: "120px" }}
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

          {error ? (
            <div style={sharedStyles.error} role="alert">
              {error}
            </div>
          ) : null}

          <div style={styles.actions}>
            <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
              {isSubmitting ? `${common("actions.create")}...` : t("createButton")}
            </button>
            <Link href="/corrective-actions" style={sharedStyles.secondaryButton}>
              {common("actions.cancel")}
            </Link>
            <span style={styles.requiredNote}>* {common("labels.required")}</span>
          </div>
        </form>
      </section>
    </PageFrame>
  );
}

function toCreateRequest(values: CorrectiveActionFormValues): CreateCorrectiveActionRequest {
  const sourceType = values.source_type || null;

  return {
    title: values.title.trim(),
    description: values.description.trim(),
    action_type: values.action_type,
    priority: values.priority,
    due_date: values.due_date,
    owner_user_id: values.owner_user_id.trim(),
    source_type: sourceType,
    source_id:
      sourceType && sourceType !== "manual" ? optionalText(values.source_id) ?? null : null,
    notes: optionalText(values.notes) ?? null,
  };
}
