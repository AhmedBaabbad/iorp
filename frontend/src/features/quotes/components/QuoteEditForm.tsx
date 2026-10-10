"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText, toDatetimeLocalValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { getQuoteById, listSamplesForQuoteCustomer, updateQuote } from "../api/quotes-api";
import type { CreateQuoteItemRequest, QuoteItem, QuoteSampleOption, QuoteStatus, UpdateQuoteRequest } from "../types";
import { QuoteItemsTable } from "./QuoteItemsTable";
import { QuoteTotals } from "./QuoteTotals";
import { useFormatter } from "@/hooks/useFormatter";
import { LineDescriptionFields, QuoteHeadingFields, UnitSelect } from "./QuoteLineFields";
import { SpecEditor } from "@/components/forms/SpecEditor";
import { ProductSelect, useBusinessSettings, useProducts } from "@/features/masterdata";

type QuoteEditValues = {
  sample_id: string;
  issue_date: string;
  valid_until: string;
  status: QuoteStatus;
  currency: string;
  discount_amount: string;
  include_tax: boolean;
  attention: string;
  subject: string;
  notes: string;
  items: QuoteItemFormValues[];
};

type QuoteItemFormValues = {
  product_type: string;
  quantity: string;
  unit: string;
  unit_price: string;
  requested_spec_json: string;
  description_ar: string;
  description_en: string;
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
  codeNote: {
    background: "var(--surface-muted)",
    border: "1px solid var(--border)",
    borderRadius: "6px",
    color: "var(--text-muted)",
    fontSize: "13px",
    padding: "10px 14px",
  },
  helper: {
    color: "var(--text-muted)",
    fontSize: "13px",
    margin: 0,
  },
};

class FormValidationError extends Error {}

const CURRENCY_OPTIONS = ["SAR", "USD"] as const;

export function QuoteEditForm() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const t = useTranslations("commercial.quotes");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const tCurrency = useTranslations("commercial.currency");
  const fmt = useFormatter();
  const quoteId = params.id;
  // MD-001: the organization's VAT rate (a quotation keeps the rate it was written with) and its products' templates.
  const { vatRate: organizationRate } = useBusinessSettings();
  const products = useProducts();
  const [savedRate, setSavedRate] = useState<number | null>(null);
  const vatRate = savedRate ?? organizationRate;

  const [values, setValues] = useState<QuoteEditValues>({
    sample_id: "",
    issue_date: toDatetimeLocalValue(new Date()),
    valid_until: toDatetimeLocalValue(new Date()),
    status: "draft",
    currency: "SAR",
    discount_amount: "",
    include_tax: false,
    attention: "",
    subject: "",
    notes: "",
    items: [createDefaultItem()],
  });
  const [customerId, setCustomerId] = useState<string>("");
  const [samples, setSamples] = useState<QuoteSampleOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadQuote() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const quote = await getQuoteById(quoteId);

        if (isMounted) {
          setCustomerId(quote.customer_id);
          const taxAmount = Number(quote.tax_amount);
          const subtotal = Number(quote.subtotal_amount);
          const discount = Number(quote.discount_amount);
          const taxableAmount = Math.max(0, subtotal - discount);
          const hasTax = quote.tax_rate != null ? Number(quote.tax_rate) > 0 : taxAmount > 0 && taxableAmount > 0;
          setSavedRate(quote.tax_rate != null && Number(quote.tax_rate) > 0 ? Number(quote.tax_rate) : null);

          setValues({
            sample_id: quote.sample_id ?? "",
            issue_date: toDatetimeLocalValue(new Date(quote.issue_date)),
            valid_until: toDatetimeLocalValue(new Date(quote.valid_until)),
            status: quote.status,
            currency: quote.currency,
            discount_amount: discount > 0 ? String(discount) : "",
            include_tax: hasTax,
            attention: quote.attention ?? "",
            subject: quote.subject ?? "",
            notes: quote.notes ?? "",
            items: quote.items.map((item) => ({
              product_type: item.product_type,
              quantity: item.quantity,
              unit: item.unit,
              unit_price: item.unit_price,
              requested_spec_json: item.requested_spec_json
                ? JSON.stringify(item.requested_spec_json, null, 2)
                : "",
              description_ar: item.description_ar ?? "",
              description_en: item.description_en ?? "",
            })),
          });
        }
      } catch (caughtError) {
        if (!isMounted) return;
        if (caughtError instanceof ApiClientError && caughtError.status === 404) {
          setIsNotFound(true);
          return;
        }
        setError(getApiErrorMessage(caughtError, messages));
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    void loadQuote();
    return () => { isMounted = false; };
  }, [quoteId, messages]);

  useEffect(() => {
    if (!customerId) return;
    let isMounted = true;

    async function loadSamples() {
      try {
        setIsLoadingSamples(true);
        const response = await listSamplesForQuoteCustomer(customerId);
        if (isMounted) setSamples(response);
      } catch {
        if (isMounted) setSamples([]);
      } finally {
        if (isMounted) setIsLoadingSamples(false);
      }
    }

    void loadSamples();
    return () => { isMounted = false; };
  }, [customerId]);

  const previewItems = useMemo(() => {
    return values.items.map((item, index) => toPreviewItem(item, index));
  }, [values.items]);

  const subtotal = useMemo(() => {
    return previewItems.reduce((sum, item) => sum + Number(item.line_total), 0);
  }, [previewItems]);

  const discountAmount = Number(values.discount_amount || 0);
  const taxableAmount = Math.max(0, subtotal - discountAmount);
  const taxAmount = values.include_tax ? taxableAmount * vatRate / 100 : 0;  // preview; the server computes it
  const totalAmount = taxableAmount + taxAmount;

  function updateField<TField extends keyof QuoteEditValues>(
    field: TField,
    value: QuoteEditValues[TField],
  ) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  function updateItemField<TField extends keyof QuoteItemFormValues>(
    index: number,
    field: TField,
    value: QuoteItemFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      items: current.items.map((item, i) => (i === index ? { ...item, [field]: value } : item)),
    }));
  }

  function addItem() {
    setValues((current) => ({ ...current, items: [...current.items, createDefaultItem()] }));
  }

  function removeItem(index: number) {
    setValues((current) => ({
      ...current,
      items: current.items.length === 1
        ? current.items
        : current.items.filter((_, i) => i !== index),
    }));
  }

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const payload: UpdateQuoteRequest = {
        sample_id: optionalText(values.sample_id) ?? null,
        issue_date: new Date(values.issue_date).toISOString(),
        valid_until: new Date(values.valid_until).toISOString(),
        currency: values.currency,
        discount_amount: Number(values.discount_amount || 0),
        tax_rate: values.include_tax ? vatRate : 0,
        tax_amount: taxAmount,
        attention: optionalText(values.attention) ?? null,
        subject: optionalText(values.subject) ?? null,
        notes: optionalText(values.notes) ?? null,
        items: values.items.map((item, index) => toItemRequest(item, index, messages)),
      };

      await updateQuote(quoteId, payload);
      setSuccessRedirect(`/quotes/${quoteId}`);
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
      title={t("editTitle")}
      subtitle={t("editTitle")}
      action={
        <Link href={`/quotes/${quoteId}`} style={sharedStyles.secondaryButton}>
          {t("backToDetail")}
        </Link>
      }
    >
      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{messages("loading.default")}</div>
      ) : null}

      {!isLoading && isNotFound ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
          <p style={{ margin: "0 0 18px" }}>{t("notFoundDescription")}</p>
          <Link href="/quotes" style={sharedStyles.button}>{t("backToList")}</Link>
        </section>
      ) : null}

      {!isLoading && !isNotFound && values.status !== "draft" ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }} role="status">
          <p style={{ margin: "0 0 12px" }}>{t("lifecycle.lockedHint")}</p>
          <Link href={`/quotes/${quoteId}`} style={sharedStyles.button}>{t("backToDetail")}</Link>
        </div>
      ) : null}

      {!isLoading && !isNotFound && values.status === "draft" ? (
        <section style={styles.panel}>
          <form style={styles.form} onSubmit={handleSubmit}>
            <div style={styles.formGrid}>
              <div style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.sample")}</span>
                <select
                  style={sharedStyles.input}
                  value={values.sample_id}
                  onChange={(event) => updateField("sample_id", event.target.value)}
                  disabled={isSubmitting || isLoadingSamples}
                >
                  <option value="">{t("fields.noSample")}</option>
                  {samples.map((sample) => (
                    <option key={sample.id} value={sample.id}>
                      {sample.sample_code} — {sample.product_type}
                    </option>
                  ))}
                </select>
              </div>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.quoteDate")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <input
                  style={sharedStyles.input}
                  type="datetime-local"
                  value={values.issue_date}
                  onChange={(event) => updateField("issue_date", event.target.value)}
                  disabled={isSubmitting}
                  required
                />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.validUntil")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <input
                  style={sharedStyles.input}
                  type="datetime-local"
                  value={values.valid_until}
                  onChange={(event) => updateField("valid_until", event.target.value)}
                  disabled={isSubmitting}
                  required
                />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.currency")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <select
                  style={sharedStyles.input}
                  value={values.currency}
                  onChange={(event) => updateField("currency", event.target.value)}
                  disabled={isSubmitting}
                  required
                >
                  {CURRENCY_OPTIONS.map((c) => (
                    <option key={c} value={c}>{tCurrency(c)}</option>
                  ))}
                </select>
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.discount")}</span>
                <input
                  style={sharedStyles.input}
                  type="number"
                  min="0"
                  step="0.01"
                  value={values.discount_amount}
                  onChange={(event) => updateField("discount_amount", event.target.value)}
                  disabled={isSubmitting}
                  placeholder={t("placeholders.discountAmount")}
                />
              </label>

              <div style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.tax")}</span>
                <label style={{ display: "flex", gap: "8px", alignItems: "center", ...sharedStyles.input }}>
                  <input
                    type="checkbox"
                    checked={values.include_tax}
                    onChange={(event) => updateField("include_tax", event.target.checked)}
                    disabled={isSubmitting}
                  />
                  <span>{t("taxCheckboxLabel", { rate: String(vatRate) })}</span>
                </label>
                {values.include_tax ? (
                  <p style={styles.helper}>{t("taxNote", { rate: String(vatRate) })} — {fmt.decimal(taxAmount)}</p>
                ) : null}
              </div>
            </div>

            <QuoteHeadingFields attention={values.attention} subject={values.subject} disabled={isSubmitting}
              onChange={(field, value) => updateField(field, value)} />

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
                      <ProductSelect style={sharedStyles.input} value={item.product_type} disabled={isSubmitting}
                        ariaLabel={t("items.fields.productType")}
                        onChange={(key, product) => {
                          updateItemField(index, "product_type", key);
                          if (product?.default_unit && !item.unit) updateItemField(index, "unit", product.default_unit);
                        }} />
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
                      <UnitSelect value={item.unit} disabled={isSubmitting}
                        onChange={(value) => updateItemField(index, "unit", value)} />
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
                        onChange={(event) => updateItemField(index, "unit_price", event.target.value)}
                        disabled={isSubmitting}
                        required
                      />
                    </label>

                    <label style={sharedStyles.field}>
                      <span style={sharedStyles.label}>{t("items.fields.lineTotal")}</span>
                      <input
                        style={sharedStyles.input}
                        value={fmt.decimal(Number(item.quantity || 0) * Number(item.unit_price || 0))}
                        disabled
                        readOnly
                      />
                    </label>
                  </div>

                  <SpecEditor value={item.requested_spec_json} disabled={isSubmitting}
                    template={products?.find((p) => p.key === item.product_type)?.properties}
                    onChange={(json) => updateItemField(index, "requested_spec_json", json)} />

                  <LineDescriptionFields arabic={item.description_ar} english={item.description_en} disabled={isSubmitting}
                    onChange={(field, value) => updateItemField(index, field, value)} />
                </section>
              ))}
            </div>

            <QuoteItemsTable items={previewItems} currency={values.currency} />
            <QuoteTotals
              totals={{
                subtotal,
                discount: discountAmount,
                tax: taxAmount,
                total: totalAmount,
                currency: values.currency,
              }}
            />

            {error ? (
              <div style={sharedStyles.error} role="alert">{error}</div>
            ) : null}

            <div style={styles.actions}>
              <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
                {isSubmitting ? messages("loading.saving") : t("updateButton")}
              </button>
              <Link href={`/quotes/${quoteId}`} style={sharedStyles.secondaryButton}>
                {common("actions.cancel")}
              </Link>
            </div>
          </form>
        </section>
      ) : null}
    </PageFrame>
    </>
  );
}

function createDefaultItem(): QuoteItemFormValues {
  return { product_type: "", quantity: "", unit: "", unit_price: "", requested_spec_json: "", description_ar: "", description_en: "" };
}

function toPreviewItem(item: QuoteItemFormValues, index: number): QuoteItem {
  return {
    line_no: index + 1,
    product_type: item.product_type || "-",
    requested_spec_json: safeParseSpec(item.requested_spec_json),
    quantity: item.quantity || "0",
    unit: item.unit,
    unit_price: item.unit_price || "0",
    line_total: String(Number(item.quantity || 0) * Number(item.unit_price || 0)),
  };
}

function toItemRequest(
  item: QuoteItemFormValues,
  index: number,
  t: (key: string) => string,
): CreateQuoteItemRequest {
  const trimmed = item.requested_spec_json.trim();
  let spec: Record<string, unknown> | null = null;
  if (trimmed) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(trimmed);
    } catch {
      throw new FormValidationError(t("validation.invalidValue"));
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new FormValidationError(t("validation.invalidValue"));
    }
    spec = parsed as Record<string, unknown>;
  }
  return {
    line_no: index + 1,
    product_type: item.product_type,
    requested_spec_json: spec,
    quantity: Number(item.quantity),
    unit: item.unit,
    unit_price: Number(item.unit_price),
    description_ar: optionalText(item.description_ar) ?? null,
    description_en: optionalText(item.description_en) ?? null,
  };
}

function safeParseSpec(value: string) {
  try {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const parsed = JSON.parse(trimmed);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}
