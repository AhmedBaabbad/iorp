"use client";

import type { CSSProperties, FormEvent } from "react";
import { useState } from "react";
import { useTranslations } from "next-intl";

import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createItem } from "../api/ncr-items-api";
import type { CreateNcrItemRequest } from "../types";

type NcrItemFormProps = {
  ncrReportId: string;
  onCreated: () => Promise<void>;
  onCancel: () => void;
};

type NcrItemFormValues = {
  item_name: string;
  issue_description: string;
  item_reference: string;
  quantity_affected: string;
  unit: string;
  notes: string;
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
  note: {
    color: "var(--text-muted)",
    fontSize: "13px",
    margin: 0,
  },
};

function createDefaultValues(): NcrItemFormValues {
  return {
    item_name: "",
    issue_description: "",
    item_reference: "",
    quantity_affected: "",
    unit: "",
    notes: "",
  };
}

export function NcrItemForm({
  ncrReportId,
  onCreated,
  onCancel,
}: NcrItemFormProps) {
  const t = useTranslations("ncr.ncrReports.items");
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const [values, setValues] = useState<NcrItemFormValues>(createDefaultValues);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [itemNameError, setItemNameError] = useState<string | null>(null);
  const [issueDescriptionError, setIssueDescriptionError] = useState<string | null>(null);

  function updateField<TField extends keyof NcrItemFormValues>(
    field: TField,
    value: NcrItemFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));

    if (field === "item_name") {
      setItemNameError(null);
    }

    if (field === "issue_description") {
      setIssueDescriptionError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setItemNameError(null);
    setIssueDescriptionError(null);

    if (!values.item_name.trim()) {
      setItemNameError(messages("validation.itemNameRequired"));
      return;
    }

    if (!values.issue_description.trim()) {
      setIssueDescriptionError(messages("validation.issueDescriptionRequired"));
      return;
    }

    setIsSubmitting(true);

    try {
      await createItem(ncrReportId, toCreateRequest(values));
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
      <p style={styles.note}>{t("lineNoAutoSentence")}</p>

      <div style={styles.formGrid}>
        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>
            {t("fields.itemName")} <span aria-hidden="true" style={{ color: "var(--danger)" }}>*</span>
          </span>
          <input
            style={sharedStyles.input}
            value={values.item_name}
            onChange={(event) => updateField("item_name", event.target.value)}
            disabled={isSubmitting}
            required
          />
          {itemNameError ? <p style={styles.inlineError}>{itemNameError}</p> : null}
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.itemReference")}</span>
          <input
            style={sharedStyles.input}
            value={values.item_reference}
            onChange={(event) => updateField("item_reference", event.target.value)}
            disabled={isSubmitting}
            placeholder={t("itemReferencePlaceholder")}
          />
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.quantityAffected")}</span>
          <input
            style={sharedStyles.input}
            type="number"
            min="0"
            step="0.01"
            value={values.quantity_affected}
            onChange={(event) => updateField("quantity_affected", event.target.value)}
            disabled={isSubmitting}
          />
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.unit")}</span>
          <input
            style={sharedStyles.input}
            value={values.unit}
            onChange={(event) => updateField("unit", event.target.value)}
            disabled={isSubmitting}
            placeholder={t("unitPlaceholder")}
          />
        </label>
      </div>

      <label style={sharedStyles.field}>
        <span style={sharedStyles.label}>
          {t("fields.issueDescription")} <span aria-hidden="true" style={{ color: "var(--danger)" }}>*</span>
        </span>
        <textarea
          style={{ ...sharedStyles.textarea, minHeight: "110px" }}
          value={values.issue_description}
          onChange={(event) => updateField("issue_description", event.target.value)}
          disabled={isSubmitting}
          placeholder={t("issueDescriptionPlaceholder")}
          required
        />
        {issueDescriptionError ? (
          <p style={styles.inlineError}>{issueDescriptionError}</p>
        ) : null}
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

      {formError ? (
        <div style={sharedStyles.error} role="alert">
          {formError}
        </div>
      ) : null}

      <div style={styles.actions}>
        <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
          {isSubmitting ? t("saving") : t("saveButton")}
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

function toCreateRequest(values: NcrItemFormValues): CreateNcrItemRequest {
  const quantityAffected = optionalText(values.quantity_affected);

  return {
    item_name: values.item_name.trim(),
    issue_description: values.issue_description.trim(),
    item_reference: optionalText(values.item_reference) ?? null,
    quantity_affected: quantityAffected ? Number(quantityAffected) : null,
    unit: quantityAffected ? optionalText(values.unit) ?? null : null,
    notes: optionalText(values.notes) ?? null,
  };
}
