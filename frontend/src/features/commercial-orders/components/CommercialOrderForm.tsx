"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { listCustomers } from "@/features/customers";
import { getQuoteById, listQuotesForCustomer } from "@/features/quotes";
import { useFormatter } from "@/hooks/useFormatter";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText, toDatetimeLocalValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type { CustomerListItem } from "@/types/customers";
import { createCommercialOrder } from "../api/commercial-orders-api";
import type { CommercialOrderItem, CreateCommercialOrderRequest } from "../types";
import { OrderItemsTable } from "./OrderItemsTable";

type QuoteOption = {
  id: string;
  customer_id: string;
  quote_number: string;
  status: string;
  currency: string;
};

type CommercialOrderFormValues = {
  customer_id: string;
  quote_id: string;
  order_date: string;
  requested_delivery_date: string;
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
  itemPanel: {
    border: "1px solid #e4e7ec",
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
    color: "#be123c",
    marginLeft: "2px",
  },
  requiredNote: {
    color: "#52606d",
    fontSize: "13px",
    marginLeft: "auto",
  },
  helper: {
    color: "#52606d",
    fontSize: "13px",
    margin: 0,
  },
};

class FormValidationError extends Error {}

export function CommercialOrderForm() {
  const router = useRouter();
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const t = useTranslations("commercial.commercialOrders");
  const tEnums = useTranslations();
  const fmt = useFormatter();
  const [values, setValues] = useState<CommercialOrderFormValues>(createDefaultValues);
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [customerQuotes, setCustomerQuotes] = useState<QuoteOption[]>([]);
  const [selectedQuoteCurrency, setSelectedQuoteCurrency] = useState("");
  const [isLoadingLookups, setIsLoadingLookups] = useState(true);
  const [isLoadingQuotes, setIsLoadingQuotes] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingQuote, setIsLoadingQuote] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadLookups() {
      try {
        setIsLoadingLookups(true);
        setLookupError(null);
        const customersResponse = await listCustomers();

        if (isMounted) {
          setCustomers(customersResponse);
          setValues((current) => ({
            ...current,
            customer_id: current.customer_id || customersResponse[0]?.id || "",
          }));
        }
      } catch (caughtError) {
        if (isMounted) {
          setLookupError(getApiErrorMessage(caughtError, messages));
        }
      } finally {
        if (isMounted) {
          setIsLoadingLookups(false);
        }
      }
    }

    void loadLookups();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadCustomerQuotes() {
      const selectedCustomerId = values.customer_id;
      setValues((current) => ({ ...current, quote_id: "" }));
      setSelectedQuoteCurrency("");

      if (!selectedCustomerId) {
        setCustomerQuotes([]);
        return;
      }

      try {
        setIsLoadingQuotes(true);
        setLookupError(null);
        const quotesResponse = await listQuotesForCustomer(selectedCustomerId);
        if (isMounted) {
          setCustomerQuotes(quotesResponse);
        }
      } catch (caughtError) {
        if (isMounted) {
          setCustomerQuotes([]);
          setLookupError(getApiErrorMessage(caughtError, messages));
        }
      } finally {
        if (isMounted) {
          setIsLoadingQuotes(false);
        }
      }
    }

    void loadCustomerQuotes();

    return () => {
      isMounted = false;
    };
  }, [values.customer_id]);

  const previewItems = useMemo(() => {
    return values.items.map((item, index) => toPreviewItem(item, index));
  }, [values.items]);

  function updateField<TField extends keyof CommercialOrderFormValues>(
    field: TField,
    value: CommercialOrderFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));
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

  async function handleQuoteChange(quoteId: string) {
    updateField("quote_id", quoteId);
    setSelectedQuoteCurrency("");

    if (!quoteId) {
      return;
    }

    setIsLoadingQuote(true);
    setError(null);

    try {
      const quote = await getQuoteById(quoteId);
      setSelectedQuoteCurrency(quote.currency);
      setValues((current) => ({
        ...current,
        quote_id: quote.id,
        customer_id: quote.customer_id,
        items: quote.items.length > 0
          ? quote.items.map((item) => ({
              product_type: item.product_type,
              quantity: item.quantity,
              unit: item.unit,
              unit_price: item.unit_price,
              requested_spec_json: item.requested_spec_json
                ? JSON.stringify(item.requested_spec_json, null, 2)
                : "",
            }))
          : current.items,
      }));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsLoadingQuote(false);
    }
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
      items: current.items.length === 1
        ? current.items
        : current.items.filter((_, itemIndex) => itemIndex !== index),
    }));
  }

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const createdOrder = await createCommercialOrder(toCreateRequest(values, messages));
      setSuccessRedirect(`/commercial-orders/${createdOrder.id}`);
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
        message={t("createSuccess")}
        okLabel={common("actions.ok")}
        onOk={() => router.replace(successRedirect)}
      />
    ) : null}
    <PageFrame
      title={t("createTitle")}
      subtitle={t("createSubtitle")}
      action={
        <Link href="/commercial-orders" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      <section style={styles.panel}>
        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={styles.formGrid}>
            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.customer")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              {customers.length > 0 ? (
                <select
                  style={sharedStyles.input}
                  value={values.customer_id}
                  onChange={(event) => updateField("customer_id", event.target.value)}
                  disabled={isSubmitting || isLoadingLookups}
                  required
                >
                  {customers.map((customer) => (
                    <option key={customer.id} value={customer.id}>
                      {customer.name} ({customer.customer_code})
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  style={sharedStyles.input}
                  value={values.customer_id}
                  onChange={(event) => updateField("customer_id", event.target.value)}
                  disabled={isSubmitting}
                  placeholder={t("fields.customer")}
                  required
                />
              )}
              {isLoadingLookups ? <p style={styles.helper}>{messages("loading.fetching")}</p> : null}
              {lookupError ? <p style={styles.helper}>{lookupError}</p> : null}
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.quote")}</span>
              <select
                style={sharedStyles.input}
                value={values.quote_id}
                onChange={(event) => void handleQuoteChange(event.target.value)}
                disabled={isSubmitting || isLoadingLookups || isLoadingQuote || isLoadingQuotes || !values.customer_id}
              >
                <option value="">
                  {!values.customer_id
                    ? t("fields.selectCustomerFirst")
                    : t("fields.noQuote")}
                </option>
                {customerQuotes.map((quote) => (
                  <option key={quote.id} value={quote.id}>
                    {quote.quote_number} — {getEnumLabel("quote", "status", quote.status, tEnums)}
                  </option>
                ))}
              </select>
              {(isLoadingQuotes || isLoadingQuote) ? (
                <p style={styles.helper}>{messages("loading.fetching")}</p>
              ) : null}
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
              <section key={index} style={styles.itemPanel} aria-label={t("items.lineTitle", { number: index + 1 })}>
                <div style={styles.itemHeader}>
                  <h3 style={{ fontSize: "16px", margin: 0 }}>{t("items.lineTitle", { number: index + 1 })}</h3>
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
                      onChange={(event) => updateItemField(index, "quantity", event.target.value)}
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
                      onChange={(event) => updateItemField(index, "unit", event.target.value)}
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

          <OrderItemsTable items={previewItems} currency={selectedQuoteCurrency} />

          {values.quote_id ? (
            <div style={{ ...sharedStyles.state, background: "#ffffff" }}>
              {t("operationalPreviewNotice")}
            </div>
          ) : null}

          {error ? (
            <div style={sharedStyles.error} role="alert">
              {error}
            </div>
          ) : null}

          <div style={styles.actions}>
            <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
              {isSubmitting ? messages("loading.saving") : common("actions.create")}
            </button>
            <Link href="/commercial-orders" style={sharedStyles.secondaryButton}>
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

function createDefaultValues(): CommercialOrderFormValues {
  const now = new Date();
  const requestedDelivery = new Date(now);
  requestedDelivery.setDate(requestedDelivery.getDate() + 14);

  return {
    customer_id: "",
    quote_id: "",
    order_date: toDatetimeLocalValue(now),
    requested_delivery_date: toDatetimeLocalValue(requestedDelivery),
    notes: "",
    items: [createDefaultItem()],
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

function toCreateRequest(
  values: CommercialOrderFormValues,
  t: (key: string) => string,
): CreateCommercialOrderRequest {
  return {
    customer_id: values.customer_id,
    quote_id: optionalText(values.quote_id) ?? null,
    order_date: new Date(values.order_date).toISOString(),
    requested_delivery_date: new Date(values.requested_delivery_date).toISOString(),
    notes: optionalText(values.notes) ?? null,
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

function toPreviewItem(item: CommercialOrderItemFormValues, index: number): CommercialOrderItem {
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
  if (!trimmed) {
    return null;
  }

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
