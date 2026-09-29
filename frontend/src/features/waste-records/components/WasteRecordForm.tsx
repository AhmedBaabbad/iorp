"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import type { CSSProperties, FormEvent } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getProductionOrders } from "@/features/production-orders";
import { getWorkCenters } from "@/features/work-centers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createWasteRecord } from "../api/waste-records-api";
import type { CreateWasteRecordRequest, WasteCategory } from "../types";
import {
  formatWasteCategory,
  wasteCategories,
} from "./waste-records-utils";

type WasteRecordFormValues = {
  production_order_id: string;
  work_center_id: string;
  shift_report_id: string;
  production_order_item_id: string;
  waste_date: string;
  quantity_wasted: string;
  unit: string;
  waste_category: WasteCategory;
  reason_code: string;
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

const defaultValues: WasteRecordFormValues = {
  production_order_id: "",
  work_center_id: "",
  shift_report_id: "",
  production_order_item_id: "",
  waste_date: "",
  quantity_wasted: "",
  unit: "",
  waste_category: "startup_loss",
  reason_code: "",
  notes: "",
};

export function WasteRecordForm() {
  const tEnums = useTranslations();
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const router = useRouter();
  const [values, setValues] = useState<WasteRecordFormValues>(defaultValues);
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
          setReferenceError(getApiErrorMessage(caughtError, messages));
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

  function updateField<TField extends keyof WasteRecordFormValues>(
    field: TField,
    value: WasteRecordFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));

    if (field === "quantity_wasted") {
      setQuantityError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setQuantityError(null);

    const quantity = Number(values.quantity_wasted);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setQuantityError("Quantity wasted must be greater than zero");
      return;
    }

    setIsSubmitting(true);

    try {
      const createdRecord = await createWasteRecord(toCreateRequest(values, quantity));
      router.replace(`/waste-records/${createdRecord.id}`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <PageFrame
      section="Production"
      title="Record waste"
      subtitle="Record waste quantity by order, work center, and category."
      action={
        <Link href="/waste-records" style={sharedStyles.secondaryButton}>
          Back to Waste Records
        </Link>
      }
    >
      <section style={styles.panel}>
        <form style={styles.form} onSubmit={handleSubmit}>
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
                Waste Date
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="date"
                value={values.waste_date}
                onChange={(event) => updateField("waste_date", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                Quantity Wasted
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="number"
                min="0.01"
                step="0.01"
                value={values.quantity_wasted}
                onChange={(event) => updateField("quantity_wasted", event.target.value)}
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
              <span style={sharedStyles.label}>
                Waste Category
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <select
                style={sharedStyles.input}
                value={values.waste_category}
                onChange={(event) =>
                  updateField("waste_category", event.target.value as WasteCategory)
                }
                disabled={isSubmitting}
                required
              >
                {wasteCategories.map((category) => (
                  <option key={category} value={category}>
                    {formatWasteCategory(category, tEnums)}
                  </option>
                ))}
              </select>
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

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Reason Code</span>
              <input
                style={sharedStyles.input}
                value={values.reason_code}
                placeholder="Describe the specific reason for this waste..."
                onChange={(event) => updateField("reason_code", event.target.value)}
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
            <Link href="/waste-records" style={sharedStyles.secondaryButton}>
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
  values: WasteRecordFormValues,
  quantity: number,
): CreateWasteRecordRequest {
  return {
    production_order_id: values.production_order_id,
    work_center_id: values.work_center_id,
    shift_report_id: optionalText(values.shift_report_id) ?? null,
    production_order_item_id: optionalText(values.production_order_item_id) ?? null,
    waste_date: values.waste_date,
    quantity_wasted: quantity,
    unit: values.unit,
    waste_category: values.waste_category,
    reason_code: optionalText(values.reason_code) ?? null,
    notes: optionalText(values.notes) ?? null,
  };
}
