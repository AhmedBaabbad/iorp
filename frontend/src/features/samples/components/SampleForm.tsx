"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { listCustomers } from "@/features/customers";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText, toDatetimeLocalValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type { CustomerListItem } from "@/types/customers";
import { createSample } from "../api/samples-api";
import type { CreateSampleRequest, RequestedSpec, SampleStatus } from "../types";

type SampleFormValues = {
  customer_id: string;
  product_type: string;
  status: SampleStatus;
  is_sample_requested: boolean;
  requested_sample_quantity: string;
  unit: string;
  request_date: string;
  requested_spec_json: string;
  notes: string;
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
  helper: {
    color: "var(--text-muted)",
    fontSize: "13px",
    margin: 0,
  },
};

const sampleStatusOptions: SampleStatus[] = [
  "requested",
  "in_preparation",
  "delivered",
  "evaluated",
  "cancelled",
];

const defaultValues: SampleFormValues = {
  customer_id: "",
  product_type: "",
  status: "requested",
  is_sample_requested: false,
  requested_sample_quantity: "",
  unit: "",
  request_date: toDatetimeLocalValue(new Date()),
  requested_spec_json: "",
  notes: "",
};

class FormValidationError extends Error {}

export function SampleForm() {
  const router = useRouter();
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const t = useTranslations("commercial.samples");
  const tEnums = useTranslations();
  const [values, setValues] = useState<SampleFormValues>(defaultValues);
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [isLoadingCustomers, setIsLoadingCustomers] = useState(true);
  const [customerLoadError, setCustomerLoadError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadCustomers() {
      try {
        setIsLoadingCustomers(true);
        setCustomerLoadError(null);
        const response = await listCustomers();

        if (isMounted) {
          setCustomers(response);
          setValues((current) => ({
            ...current,
            customer_id: current.customer_id || response[0]?.id || "",
          }));
        }
      } catch (caughtError) {
        if (isMounted) {
          setCustomerLoadError(getApiErrorMessage(caughtError, messages));
        }
      } finally {
        if (isMounted) {
          setIsLoadingCustomers(false);
        }
      }
    }

    void loadCustomers();

    return () => {
      isMounted = false;
    };
  }, []);

  function updateField<TField extends keyof SampleFormValues>(
    field: TField,
    value: SampleFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
      ...(field === "is_sample_requested" && value === false
        ? { requested_sample_quantity: "", unit: "" }
        : {}),
    }));
  }

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const createdSample = await createSample(toCreateRequest(values, messages));
      setSuccessRedirect(`/samples/${createdSample.id}`);
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
        <Link href="/samples" style={sharedStyles.secondaryButton}>
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
                  disabled={isSubmitting || isLoadingCustomers}
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
                  placeholder={t("placeholders.customerId")}
                  required
                />
              )}
              {isLoadingCustomers ? <p style={styles.helper}>{messages("loading.fetching")}</p> : null}
              {customerLoadError ? <p style={styles.helper}>{customerLoadError}</p> : null}
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.productType")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                value={values.product_type}
                onChange={(event) => updateField("product_type", event.target.value)}
                maxLength={120}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.status")}</span>
              <select
                style={sharedStyles.input}
                value={values.status}
                onChange={(event) =>
                  updateField("status", event.target.value as SampleStatus)
                }
                disabled={isSubmitting}
              >
                {sampleStatusOptions.map((s) => (
                  <option key={s} value={s} disabled={s === "evaluated"}>
                    {getEnumLabel("sample", "status", s, tEnums)}
                  </option>
                ))}
              </select>
            </label>

            <label style={{ ...sharedStyles.field, alignSelf: "end" }}>
              <span style={sharedStyles.label}>{t("fields.isSampleRequested")}</span>
              <label style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={values.is_sample_requested}
                  onChange={(event) => updateField("is_sample_requested", event.target.checked)}
                  disabled={isSubmitting}
                />
                <span>{t("labels.sampleRequested")}</span>
              </label>
            </label>

            {values.is_sample_requested ? (
              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.requestedSampleQuantity")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <input
                  style={sharedStyles.input}
                  type="number"
                  step="0.01"
                  min="0"
                  value={values.requested_sample_quantity}
                  onChange={(event) => updateField("requested_sample_quantity", event.target.value)}
                  disabled={isSubmitting}
                  required
                />
              </label>
            ) : null}

            {values.is_sample_requested ? (
              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.unit")}
                  <span style={styles.required} aria-hidden="true"> *</span>
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
            ) : null}

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                {t("fields.requestDate")}
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                type="datetime-local"
                value={values.request_date}
                onChange={(event) => updateField("request_date", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>
          </div>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.requestedSpecJson")}</span>
            <textarea
              style={{ ...sharedStyles.textarea, minHeight: "130px", fontFamily: "monospace" }}
              value={values.requested_spec_json}
              onChange={(event) => updateField("requested_spec_json", event.target.value)}
              disabled={isSubmitting}
              placeholder={'{"color":"blue","thickness":"50 micron"}'}
            />
          </label>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.notes")}</span>
            <textarea
              style={{ ...sharedStyles.textarea, minHeight: "110px" }}
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
              {isSubmitting ? messages("loading.saving") : common("actions.create")}
            </button>
            <Link href="/samples" style={sharedStyles.secondaryButton}>
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

function toCreateRequest(
  values: SampleFormValues,
  t: (key: string) => string,
): CreateSampleRequest {
  return {
    customer_id: values.customer_id,
    product_type: values.product_type,
    status: values.status,
    is_sample_requested: values.is_sample_requested,
    requested_sample_quantity: values.is_sample_requested
      ? Number(values.requested_sample_quantity)
      : null,
    unit: values.is_sample_requested ? optionalText(values.unit) : null,
    request_date: new Date(values.request_date).toISOString(),
    requested_spec_json: parseRequestedSpec(values.requested_spec_json, t),
    notes: optionalText(values.notes) ?? null,
  };
}

function parseRequestedSpec(
  value: string,
  t: (key: string) => string,
): RequestedSpec | null {
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

  return parsed as RequestedSpec;
}
