"use client";

import type { CSSProperties, FormEvent } from "react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createItem } from "../api/production-order-items-api";
import type { CreateProductionOrderItemRequest } from "../types";
import { formatStatus, isReadOnlyStatus } from "./production-order-items-utils";

type ProductionOrderItemFormProps = {
  productionOrderId: string;
  productionOrderStatus: string;
  onCreated: () => Promise<void>;
};

type ProductionOrderItemFormValues = {
  planned_quantity: string;
  unit: string;
  target_spec_json: string;
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
  button: {
    ...sharedStyles.button,
    width: "fit-content",
  },
  helper: {
    color: "#52606d",
    fontSize: "13px",
    margin: 0,
  },
};

const defaultValues: ProductionOrderItemFormValues = {
  planned_quantity: "",
  unit: "kg",
  target_spec_json: "",
  notes: "",
};

class FormValidationError extends Error {}

export function ProductionOrderItemForm({
  productionOrderId,
  productionOrderStatus,
  onCreated,
}: ProductionOrderItemFormProps) {
  const t = useTranslations("production.productionOrders.items");
  const messages = useTranslations("messages");
  const [values, setValues] = useState<ProductionOrderItemFormValues>(defaultValues);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  if (isReadOnlyStatus(productionOrderStatus)) {
    return (
      <div style={sharedStyles.state}>
        {t("formStatusGuardMessage", { status: formatStatus(productionOrderStatus) })}
      </div>
    );
  }

  function updateField<TField extends keyof ProductionOrderItemFormValues>(
    field: TField,
    value: ProductionOrderItemFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setIsSubmitting(true);

    try {
      await createItem(productionOrderId, toCreateRequest(values, t));
      setValues(defaultValues);
      await onCreated();
    } catch (caughtError) {
      setFormError(
        caughtError instanceof FormValidationError
          ? caughtError.message
          : getApiErrorMessage(caughtError, messages),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form style={styles.form} onSubmit={handleSubmit}>
      <div style={sharedStyles.state}>{t("lineNumberAutoSentence")}</div>

      <div style={styles.formGrid}>
        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>
            {t("fields.plannedQuantity")} <span aria-hidden="true" style={{ color: "#be123c" }}>*</span>
          </span>
          <input
            style={sharedStyles.input}
            type="number"
            min="0.01"
            step="0.01"
            value={values.planned_quantity}
            onChange={(event) => updateField("planned_quantity", event.target.value)}
            disabled={isSubmitting}
            required
          />
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>
            {t("fields.unit")} <span aria-hidden="true" style={{ color: "#be123c" }}>*</span>
          </span>
          <input
            style={sharedStyles.input}
            value={values.unit}
            onChange={(event) => updateField("unit", event.target.value)}
            maxLength={32}
            disabled={isSubmitting}
            required
          />
        </label>
      </div>

      <label style={sharedStyles.field}>
        <span style={sharedStyles.label}>{t("lineSpecifications")}</span>
        <textarea
          style={sharedStyles.textarea}
          value={values.target_spec_json}
          onChange={(event) => updateField("target_spec_json", event.target.value)}
          disabled={isSubmitting}
          placeholder='{"width": "50cm"}'
        />
        <p style={styles.helper}>
          {t("lineSpecificationsHelper", { example: "{\"width\": \"50cm\"}" })}
        </p>
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

      <button style={styles.button} type="submit" disabled={isSubmitting}>
        {isSubmitting ? t("adding") : t("addButton")}
      </button>
    </form>
  );
}

function toCreateRequest(
  values: ProductionOrderItemFormValues,
  t: (key: string) => string,
): CreateProductionOrderItemRequest {
  return {
    target_spec_json: parseTargetSpecJson(values.target_spec_json, t),
    planned_quantity: Number(values.planned_quantity),
    unit: values.unit,
    notes: optionalText(values.notes) ?? null,
  };
}

function parseTargetSpecJson(value: string, t: (key: string) => string) {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return null;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new FormValidationError(t("lineSpecValidJsonError"));
  }

  if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new FormValidationError(t("lineSpecObjectError"));
  }

  return parsed as Record<string, unknown>;
}
