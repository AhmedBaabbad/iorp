"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useMemo, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { useFormatter } from "@/hooks/useFormatter";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText, toDatetimeLocalValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { updateCommercialOrder } from "../api/commercial-orders-api";
import type {
  CommercialOrderData,
  CommercialOrderItem,
  CommercialOrderStatus,
  UpdateCommercialOrderRequest,
} from "../types";
import { OrderItemsTable } from "./OrderItemsTable";

type CommercialOrderEditFormValues = {
  order_date: string;
  requested_delivery_date: string;
  status: CommercialOrderStatus;
  notes: string;
  items: CommercialOrderItemFormValues[];
};

type CommercialOrderItemFormValues = {
  product_type: string;
  quantity: string;
  unit: string;
  unit_price: string;
  requested_spec_json: string;
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
  itemPanel: {
    border: "1px solid var(--border)",
    borderRadius: "8px",
    display: "grid",
    gap: "16px",
    padding: "18px",
  },
  itemHeader: {
    alignItems: "center",
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
    justifyContent: "space-between",
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

const ORDER_STATUSES: CommercialOrderStatus[] = [
  "draft",
  "confirmed",
  "cancelled",
  "converted_to_production",
];

class FormValidationError extends Error {}

type Props = { order: CommercialOrderData };

export function CommercialOrderEditForm({ order }: Props) {
  const router = useRouter();
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const t = useTranslations("commercial.commercialOrders");
  const tEnums = useTranslations();
  const fmt = useFormatter();
  const [values, setValues] = useState<CommercialOrderEditFormValues>(() =>
    toFormValues(order),
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);

  const previewItems = useMemo(
    () => values.items.map((item, index) => toPreviewItem(item, index)),
    [values.items],
  );

  function updateField<TField extends keyof CommercialOrderEditFormValues>(
    field: TField,
    value: CommercialOrderEditFormValues[TField],
  ) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  function updateItemField<TField extends keyof CommercialOrderItemFormValues>(
    index: number,
    field: TField,
    value: CommercialOrderItemFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: value } : item,
      ),
    }));
  }

  function addItem() {
    setValues((current) => ({
      ...current,
      items: [...current.items, createDefaultItem()],
    }));
  }

  function removeItem(index: number) {
    setValues((current) => ({
      ...current,
      items:
        current.items.length === 1
          ? current.items
          : current.items.filter((_, i) => i !== index),
    }));
  }

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await updateCommercialOrder(order.id, toUpdateRequest(values, messages));
      setSuccessRedirect(`/commercial-orders/${order.id}`);
    } catch (caughtError) {
      setError(
        caughtError instanceof FormValidationError
          ? caughtError.message
          : getApiErrorMessage(caughtError, messages),
      );
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
        title={`${t("editTitle")} — ${order.order_number}`}
        subtitle={t("detailSubtitle")}
        action={
          <Link
            href={`/commercial-orders/${order.id}`}
            style={sharedStyles.secondaryButton}
          >
            {t("backToDetail")}
          </Link>
        }
      >
        <section style={styles.panel}>
          <form style={styles.form} onSubmit={handleSubmit}>
            <div style={styles.formGrid}>
              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.status")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <select
                  style={sharedStyles.input}
                  value={values.status}
                  onChange={(event) =>
                    updateField("status", event.target.value as CommercialOrderStatus)
                  }
                  disabled={isSubmitting}
                  required
                >
                  {ORDER_STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {getEnumLabel("commercialOrder", "status", status, tEnums)}
                    </option>
                  ))}
                </select>
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.orderDate")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <input
                  style={sharedStyles.input}
                  type="datetime-local"
                  value={values.order_date}
                  onChange={(event) => updateField("order_date", event.target.value)}
                  disabled={isSubmitting}
                  required
                />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.requestedDelivery")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <input
                  style={sharedStyles.input}
                  type="datetime-local"
                  value={values.requested_delivery_date}
                  onChange={(event) =>
                    updateField("requested_delivery_date", event.target.value)
                  }
                  disabled={isSubmitting}
                  required
                />
              </label>
            </div>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.notes")}</span>
              <textarea
                style={{ ...sharedStyles.textarea, minHeight: "100px" }}
                value={values.notes}
                onChange={(event) => updateField("notes", event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            <div style={{ display: "grid", gap: "16px" }}>
              <div style={styles.itemHeader}>
                <h2 style={{ fontSize: "20px", margin: 0 }}>{t("items.sectionTitle")}</h2>
                <button
                  style={sharedStyles.secondaryButton}
                  type="button"
                  onClick={addItem}
                  disabled={isSubmitting}
                >
                  {t("items.addButton")}
                </button>
              </div>

              {values.items.map((item, index) => (
                <section
                  key={index}
                  style={styles.itemPanel}
                  aria-label={t("items.lineTitle", { number: index + 1 })}
                >
                  <div style={styles.itemHeader}>
                    <h3 style={{ fontSize: "16px", margin: 0 }}>
                      {t("items.lineTitle", { number: index + 1 })}
                    </h3>
                    <button
                      style={sharedStyles.secondaryButton}
                      type="button"
                      onClick={() => removeItem(index)}
                      disabled={isSubmitting || values.items.length === 1}
                    >
                      {t("items.removeButton")}
                    </button>
                  </div>

                  <div style={styles.formGrid}>
                    <label style={sharedStyles.field}>
                      <span style={sharedStyles.label}>
                        {t("items.fields.productType")}
                        <span style={styles.required} aria-hidden="true"> *</span>
                      </span>
                      <input
                        style={sharedStyles.input}
                        value={item.product_type}
                        onChange={(event) =>
                          updateItemField(index, "product_type", event.target.value)
                        }
                        maxLength={120}
                        disabled={isSubmitting}
                        required
                      />
                    </label>

                    <label style={sharedStyles.field}>
                      <span style={sharedStyles.label}>
                        {t("items.fields.quantity")}
                        <span style={styles.required} aria-hidden="true"> *</span>
                      </span>
                      <input
                        style={sharedStyles.input}
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={item.quantity}
                        onChange={(event) =>
                          updateItemField(index, "quantity", event.target.value)
                        }
                        disabled={isSubmitting}
                        required
                      />
                    </label>

                    <label style={sharedStyles.field}>
                      <span style={sharedStyles.label}>
                        {t("items.fields.unit")}
                        <span style={styles.required} aria-hidden="true"> *</span>
                      </span>
                      <input
                        style={sharedStyles.input}
                        value={item.unit}
                        onChange={(event) =>
                          updateItemField(index, "unit", event.target.value)
                        }
                        maxLength={32}
                        disabled={isSubmitting}
                        required
                      />
                    </label>

                    <label style={sharedStyles.field}>
                      <span style={sharedStyles.label}>
                        {t("items.fields.unitPrice")}
                        <span style={styles.required} aria-hidden="true"> *</span>
                      </span>
                      <input
                        style={sharedStyles.input}
                        type="number"
                        step="0.01"
                        min="0"
                        value={item.unit_price}
                        onChange={(event) =>
                          updateItemField(index, "unit_price", event.target.value)
                        }
                        disabled={isSubmitting}
                        required
                      />
                    </label>

                    <label style={sharedStyles.field}>
                      <span style={sharedStyles.label}>{t("items.fields.lineTotal")}</span>
                      <input
                        style={sharedStyles.input}
                        value={fmt.decimal(calculateLineTotal(item))}
                        disabled
                        readOnly
                      />
                    </label>
                  </div>

                  <label style={sharedStyles.field}>
                    <span style={sharedStyles.label}>{t("fields.requestedSpecJson")}</span>
                    <textarea
                      style={{ ...sharedStyles.textarea, fontFamily: "monospace" }}
                      value={item.requested_spec_json}
                      onChange={(event) =>
                        updateItemField(index, "requested_spec_json", event.target.value)
                      }
                      disabled={isSubmitting}
                      placeholder={'{"grade":"A","color":"blue"}'}
                    />
                  </label>
                </section>
              ))}
            </div>

            <OrderItemsTable items={previewItems} currency="" />

            {error ? (
              <div style={sharedStyles.error} role="alert">
                {error}
              </div>
            ) : null}

            <div style={styles.actions}>
              <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
                {isSubmitting ? messages("loading.saving") : t("updateButton")}
              </button>
              <Link
                href={`/commercial-orders/${order.id}`}
                style={sharedStyles.secondaryButton}
              >
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

function toFormValues(order: CommercialOrderData): CommercialOrderEditFormValues {
  return {
    order_date: toDatetimeLocalValue(new Date(order.order_date)),
    requested_delivery_date: order.requested_delivery_date
      ? toDatetimeLocalValue(new Date(order.requested_delivery_date))
      : "",
    status: order.status,
    notes: order.notes ?? "",
    items:
      order.items.length > 0
        ? order.items.map((item) => ({
            product_type: item.product_type,
            quantity: item.quantity,
            unit: item.unit,
            unit_price: item.agreed_unit_price ?? "",
            requested_spec_json: item.requested_spec_json
              ? JSON.stringify(item.requested_spec_json, null, 2)
              : "",
          }))
        : [createDefaultItem()],
  };
}

function createDefaultItem(): CommercialOrderItemFormValues {
  return {
    product_type: "",
    quantity: "",
    unit: "",
    unit_price: "",
    requested_spec_json: "",
  };
}

function toUpdateRequest(
  values: CommercialOrderEditFormValues,
  t: (key: string) => string,
): UpdateCommercialOrderRequest {
  return {
    order_date: new Date(values.order_date).toISOString(),
    requested_delivery_date: values.requested_delivery_date
      ? new Date(values.requested_delivery_date).toISOString()
      : null,
    notes: optionalText(values.notes) ?? null,
    status: values.status,
    items: values.items.map((item, index) => ({
      line_no: index + 1,
      product_type: item.product_type,
      requested_spec_json: parseRequestedSpec(item.requested_spec_json, t),
      quantity: Number(item.quantity),
      unit: item.unit,
      agreed_unit_price: Number(item.unit_price),
    })),
  };
}

function toPreviewItem(
  item: CommercialOrderItemFormValues,
  index: number,
): CommercialOrderItem {
  return {
    line_no: index + 1,
    product_type: item.product_type || "-",
    requested_spec_json: safeParseRequestedSpec(item.requested_spec_json),
    quantity: item.quantity || "0",
    unit: item.unit,
    agreed_unit_price: item.unit_price || "0",
    line_total: String(calculateLineTotal(item)),
  };
}

function calculateLineTotal(item: CommercialOrderItemFormValues) {
  return Number(item.quantity || 0) * Number(item.unit_price || 0);
}

function parseRequestedSpec(value: string, t: (key: string) => string) {
  const trimmed = value.trim();
  if (!trimmed) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new FormValidationError(t("validation.invalidValue"));
  }

  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new FormValidationError(t("validation.invalidValue"));
  }

  return parsed as Record<string, unknown>;
}

function safeParseRequestedSpec(value: string) {
  try {
    return parseRequestedSpec(value, () => "");
  } catch {
    return null;
  }
}
