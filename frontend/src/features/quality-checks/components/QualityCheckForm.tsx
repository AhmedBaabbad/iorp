"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import type { CSSProperties, FormEvent } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getProductionOrders } from "@/features/production-orders";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createQualityCheck } from "../api/quality-checks-api";
import type {
  CreateQualityCheckRequest,
  QualityCheckType,
} from "../types";

type QualityCheckFormValues = {
  check_type: QualityCheckType;
  check_date: string;
  qty_inspected: string;
  qty_accepted: string;
  qty_rejected: string;
  production_order_id: string;
  production_order_item_id: string;
  notes: string;
};

type ProductionOrderOption = {
  id: string;
  production_order_number: string;
  product_type: string;
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
  inlineError: {
    color: "var(--danger)",
    fontSize: "13px",
    margin: 0,
  },
};

const defaultValues: QualityCheckFormValues = {
  check_type: "in_process_inspection",
  check_date: new Date().toISOString().slice(0, 10),
  qty_inspected: "",
  qty_accepted: "0",
  qty_rejected: "0",
  production_order_id: "",
  production_order_item_id: "",
  notes: "",
};

export function QualityCheckForm() {
  const t = useTranslations("quality.qualityChecks");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const router = useRouter();
  const [values, setValues] = useState<QualityCheckFormValues>(defaultValues);
  const [productionOrders, setProductionOrders] = useState<ProductionOrderOption[]>([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState(true);
  const [referenceError, setReferenceError] = useState<string | null>(null);
  const [quantityError, setQuantityError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadProductionOrders() {
      try {
        setIsLoadingOrders(true);
        setReferenceError(null);
        const response = await getProductionOrders();

        if (isMounted) {
          setProductionOrders(response);
        }
      } catch (caughtError) {
        if (isMounted) {
          setReferenceError(
            getApiErrorMessage(caughtError, messages),
          );
        }
      } finally {
        if (isMounted) {
          setIsLoadingOrders(false);
        }
      }
    }

    void loadProductionOrders();

    return () => {
      isMounted = false;
    };
  }, [t]);

  function updateField<TField extends keyof QualityCheckFormValues>(
    field: TField,
    value: QualityCheckFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));
    if (field === "qty_inspected" || field === "qty_accepted" || field === "qty_rejected") {
      setQuantityError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setQuantityError(null);

    const validationError = validateQuantities(values, t);
    if (validationError) {
      setQuantityError(validationError);
      return;
    }

    setIsSubmitting(true);

    try {
      const createdCheck = await createQualityCheck(toCreateRequest(values));
      router.replace(`/quality-checks/${createdCheck.id}`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <PageFrame
      section="Quality"
      title={t("createTitle")}
      subtitle={t("createSubtitle")}
      action={
        <Link href="/quality-checks" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      <section style={styles.panel}>
        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={sharedStyles.state}>{t("inspectionCodeAutoSentence")}</div>

          <div style={styles.formGrid}>
            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.checkType")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <select
                style={sharedStyles.input}
                value={values.check_type}
                onChange={(event) =>
                  updateField("check_type", event.target.value as QualityCheckType)
                }
                disabled={isSubmitting}
                required
              >
                <option value="in_process_inspection">In-Process Inspection</option>
                <option value="finished_product_inspection">Finished Product Inspection</option>
                <option value="sample_inspection">Sample Inspection</option>
                <option value="reinspection">Re-inspection</option>
                <option value="issue_triggered">Issue Triggered</option>
                <option value="general">General</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.checkDate")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="date"
                value={values.check_date}
                onChange={(event) => updateField("check_date", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.qtyInspected")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="number"
                min="1"
                step="1"
                value={values.qty_inspected}
                onChange={(event) => updateField("qty_inspected", event.target.value)}
                disabled={isSubmitting}
                required
              />
              {quantityError ? <p style={styles.inlineError}>{quantityError}</p> : null}
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.qtyAccepted")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="number"
                min="0"
                step="1"
                value={values.qty_accepted}
                onChange={(event) => updateField("qty_accepted", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.qtyRejected")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="number"
                min="0"
                step="1"
                value={values.qty_rejected}
                onChange={(event) => updateField("qty_rejected", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.productionOrder")}</span>
              <select
                style={sharedStyles.input}
                value={values.production_order_id}
                onChange={(event) => updateField("production_order_id", event.target.value)}
                disabled={isSubmitting || isLoadingOrders}
              >
                <option value="">
                  {isLoadingOrders ? t("loadingProductionOrders") : t("noProductionOrderSelected")}
                </option>
                {productionOrders.map((order) => (
                  <option key={order.id} value={order.id}>
                    {order.production_order_number} - {order.product_type}
                  </option>
                ))}
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.productionOrderItemId")}</span>
              <input
                style={sharedStyles.input}
                value={values.production_order_item_id}
                onChange={(event) =>
                  updateField("production_order_item_id", event.target.value)
                }
                disabled={isSubmitting}
              />
            </label>
          </div>

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

          {error ? (
            <div style={sharedStyles.error} role="alert">
              {error}
            </div>
          ) : null}

          <div style={styles.actions}>
            <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
              {isSubmitting ? t("creating") : t("createButton")}
            </button>
            <Link href="/quality-checks" style={sharedStyles.secondaryButton}>
              {common("actions.cancel")}
            </Link>
            <span style={styles.requiredNote}>* {common("labels.required")}</span>
          </div>
        </form>
      </section>
    </PageFrame>
  );
}

function validateQuantities(
  values: QualityCheckFormValues,
  t: (key: string) => string,
) {
  const qtyInspected = Number(values.qty_inspected);
  const qtyAccepted = Number(values.qty_accepted);
  const qtyRejected = Number(values.qty_rejected);

  if (qtyInspected <= 0) {
    return t("qtyInspectedPositive");
  }

  if (qtyAccepted + qtyRejected !== qtyInspected) {
    return t("qtyConstraint");
  }

  return null;
}

function toCreateRequest(values: QualityCheckFormValues): CreateQualityCheckRequest {
  return {
    production_order_id: optionalText(values.production_order_id) ?? null,
    production_order_item_id: optionalText(values.production_order_item_id) ?? null,
    check_datetime: `${values.check_date}T00:00:00`,
    check_type: values.check_type,
    qty_inspected: Number(values.qty_inspected),
    qty_accepted: Number(values.qty_accepted),
    qty_rejected: Number(values.qty_rejected),
    notes: optionalText(values.notes) ?? null,
  };
}
