"use client";

import Link from "next/link";
import { useAuth } from '@/features/auth';
import { SAMPLE_STATUS_PERMISSION } from '../permissions';
import { UnitSelect } from "@/components/forms/UnitSelect";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { CustomerPicker } from "@/features/customers";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { optionalText, toDatetimeLocalValue } from "@/lib/utils";
import { sampleError } from "./sample-errors";
import { SampleProductFields } from "./SampleProperties";
import { sharedStyles } from "@/styles/shared-styles";
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
  property_values: RequestedSpec;
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
  property_values: {},
  notes: "",
};


export function SampleForm() {
  const { hasPermission } = useAuth();
  const router = useRouter();
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const t = useTranslations("commercial.samples");
  const tEnums = useTranslations();
  const [values, setValues] = useState<SampleFormValues>(defaultValues);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [specReady, setSpecReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);

  // ARCH-PAGE-001: the customer is chosen with CustomerPicker (a search), never by loading every customer.

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
      const createdSample = await createSample(toCreateRequest(values));
      setSuccessRedirect(`/samples/${createdSample.id}`);
    } catch (caughtError) {
      setError(
        sampleError(caughtError, t, messages),
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
              <CustomerPicker value={values.customer_id} disabled={isSubmitting}
                onChange={(id) => updateField("customer_id", id)} />
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
                {sampleStatusOptions.filter(s => s === 'requested' || hasPermission(SAMPLE_STATUS_PERMISSION[s])).map((s) => (
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
                <UnitSelect value={values.unit} onChange={(unit) => updateField("unit", unit)}
                  disabled={isSubmitting} ariaLabel={t("fields.unit")} />
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
          <SampleProductFields productKey={values.product_type} values={values.property_values} disabled={isSubmitting} onReady={setSpecReady}
            onChange={(key, specs, unit) => { setValues(v => ({ ...v, product_type: key, property_values: specs, ...(unit !== undefined ? { unit: unit ?? "" } : {}) })); }} />


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
            <button style={sharedStyles.button} type="submit" disabled={isSubmitting || !specReady}>
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
    property_values: values.property_values,
    notes: optionalText(values.notes) ?? null,
  };
}

