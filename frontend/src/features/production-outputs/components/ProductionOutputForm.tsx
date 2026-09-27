"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties, FormEvent } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getProductionOrders } from "@/features/production-orders";
import { getWorkCenters } from "@/features/work-centers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createProductionOutput } from "../api/production-outputs-api";
import type { CreateProductionOutputRequest } from "../types";

type ProductionOutputFormValues = {
  production_order_id: string;
  work_center_id: string;
  shift_report_id: string;
  production_order_item_id: string;
  output_date: string;
  quantity_produced: string;
  unit: string;
  recorded_at: string;
  notes: string;
};

type WorkCenterOption = {
  id: string;
  code: string;
  name: string;
};

type ProductionOrderOption = {
  id: string;
  production_order_number: string;
  product_type: string;
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

const defaultValues: ProductionOutputFormValues = {
  production_order_id: "",
  work_center_id: "",
  shift_report_id: "",
  production_order_item_id: "",
  output_date: "",
  quantity_produced: "",
  unit: "",
  recorded_at: "",
  notes: "",
};

export function ProductionOutputForm() {
  const router = useRouter();
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const [values, setValues] = useState<ProductionOutputFormValues>(defaultValues);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [productionOrders, setProductionOrders] = useState<ProductionOrderOption[]>([]);
  const [isLoadingReferences, setIsLoadingReferences] = useState(true);
  const [referenceError, setReferenceError] = useState<string | null>(null);
  const [quantityError, setQuantityError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadReferences() {
      try {
        setIsLoadingReferences(true);
        setReferenceError(null);

        const [workCentersResponse, productionOrdersResponse] = await Promise.all([
          getWorkCenters().catch(() => []),
          getProductionOrders().catch(() => []),
        ]);

        if (isMounted) {
          setWorkCenters(workCentersResponse);
          setProductionOrders(productionOrdersResponse);
          setValues((current) => ({
            ...current,
            work_center_id: current.work_center_id || workCentersResponse[0]?.id || "",
            production_order_id:
              current.production_order_id || productionOrdersResponse[0]?.id || "",
          }));
        }
      } catch (caughtError) {
        if (isMounted) {
          setReferenceError(
            getApiErrorMessage(caughtError, messages),
          );
        }
      } finally {
        if (isMounted) {
          setIsLoadingReferences(false);
        }
      }
    }

    void loadReferences();

    return () => {
      isMounted = false;
    };
  }, []);

  function updateField<TField extends keyof ProductionOutputFormValues>(
    field: TField,
    value: ProductionOutputFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));

    if (field === "quantity_produced") {
      setQuantityError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setQuantityError(null);

    const quantity = Number(values.quantity_produced);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setQuantityError("Quantity produced must be greater than zero");
      return;
    }

    setIsSubmitting(true);

    try {
      const createdOutput = await createProductionOutput(toCreateRequest(values, quantity));
      router.replace(`/production-outputs/${createdOutput.id}`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <PageFrame
      section="Production"
      title="Record production output"
      subtitle="Record produced quantity against a production order and work center."
      action={
        <Link href="/production-outputs" style={sharedStyles.secondaryButton}>
          Back to Production Outputs
        </Link>
      }
    >
      <section style={styles.panel}>
        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={sharedStyles.state}>
            Status: Recorded on creation
          </div>

          <div style={styles.formGrid}>
            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                Production Order
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <select
                style={sharedStyles.input}
                value={values.production_order_id}
                onChange={(event) => updateField("production_order_id", event.target.value)}
                disabled={
                  isSubmitting || isLoadingReferences || productionOrders.length === 0
                }
                required
              >
                {isLoadingReferences ? (
                  <option value="">{messages("loading.fetching")}</option>
                ) : null}
                {!isLoadingReferences && productionOrders.length === 0 ? (
                  <option value="">No production orders available</option>
                ) : null}
                {productionOrders.map((order) => (
                  <option key={order.id} value={order.id}>
                    {order.production_order_number} - {order.product_type}
                  </option>
                ))}
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                Work Center
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <select
                style={sharedStyles.input}
                value={values.work_center_id}
                onChange={(event) => updateField("work_center_id", event.target.value)}
                disabled={isSubmitting || isLoadingReferences || workCenters.length === 0}
                required
              >
                {isLoadingReferences ? <option value="">{messages("loading.fetching")}</option> : null}
                {!isLoadingReferences && workCenters.length === 0 ? (
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
                Output Date
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="date"
                value={values.output_date}
                onChange={(event) => updateField("output_date", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                Quantity Produced
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="number"
                min="0.01"
                step="0.01"
                value={values.quantity_produced}
                onChange={(event) => updateField("quantity_produced", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                Unit
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                value={values.unit}
                placeholder="kg, pcs, m, roll"
                onChange={(event) => updateField("unit", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Recorded At</span>
              <input
                style={sharedStyles.input}
                type="datetime-local"
                value={values.recorded_at}
                onChange={(event) => updateField("recorded_at", event.target.value)}
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
              <span style={sharedStyles.label}>Production Order Item ID</span>
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

          {quantityError ? (
            <div style={sharedStyles.error} role="alert">
              {quantityError}
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
                isLoadingReferences ||
                workCenters.length === 0 ||
                productionOrders.length === 0
              }
            >
              {isSubmitting ? messages("loading.saving") : common("actions.create")}
            </button>
            <Link href="/production-outputs" style={sharedStyles.secondaryButton}>
              {common("actions.cancel")}
            </Link>
            <span style={styles.requiredNote}>* {common("labels.required")}</span>
          </div>
        </form>
      </section>
    </PageFrame>
  );
}

function toCreateRequest(
  values: ProductionOutputFormValues,
  quantity: number,
): CreateProductionOutputRequest {
  return {
    production_order_id: values.production_order_id,
    work_center_id: values.work_center_id,
    shift_report_id: optionalText(values.shift_report_id) ?? null,
    production_order_item_id: optionalText(values.production_order_item_id) ?? null,
    output_date: values.output_date,
    recorded_at: toOptionalIsoDatetime(values.recorded_at),
    quantity_produced: quantity,
    unit: values.unit,
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
