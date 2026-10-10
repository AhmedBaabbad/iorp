"use client";

import Link from "next/link";
import { useAuth } from '@/features/auth';
import { SAMPLE_STATUS_PERMISSION } from '../permissions';
import { UnitSelect } from "@/components/forms/UnitSelect";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText, toDatetimeLocalValue } from "@/lib/utils";
import { sampleError } from "./sample-errors";
import { SampleProductFields } from "./SampleProperties";
import { sharedStyles } from "@/styles/shared-styles";
import { getSampleById, updateSample } from "../api/samples-api";
import type { SampleProductDefinition, RequestedSpec, SampleDecision, SampleStatus, UpdateSampleRequest } from "../types";

type SampleEditValues = {
  product_type: string;
  status: SampleStatus;
  sample_decision: SampleDecision;
  is_sample_requested: boolean;
  requested_sample_quantity: string;
  unit: string;
  request_date: string;
  property_values: RequestedSpec;
  notes: string;
};

const sampleStatusEditOptions: SampleStatus[] = [
  "requested",
  "in_preparation",
  "delivered",
  "evaluated",
  "cancelled",
];

const sampleDecisionOptions: SampleDecision[] = ["pending", "accepted", "rejected"];

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

const defaultValues: SampleEditValues = {
  product_type: "",
  status: "requested",
  sample_decision: "pending",
  is_sample_requested: false,
  requested_sample_quantity: "",
  unit: "",
  request_date: toDatetimeLocalValue(new Date()),
  property_values: {},
  notes: "",
};


export function SampleEditForm() {
  const { hasPermission } = useAuth();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const t = useTranslations("commercial.samples");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const tEnums = useTranslations();
  const sampleId = params.id;
  const [values, setValues] = useState<SampleEditValues>(defaultValues);
  const [initialStatus, setInitialStatus] = useState<SampleStatus | null>(null);
  const [sampleCode, setSampleCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [specReady, setSpecReady] = useState(false);
  const [specChanged, setSpecChanged] = useState(false);
  const [productDefinition, setProductDefinition] = useState<SampleProductDefinition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadSample() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const sample = await getSampleById(sampleId);

        if (isMounted) {
          setProductDefinition(sample.product_definition ?? null);
          setSpecChanged(false);
          setSampleCode(sample.sample_code);
          setInitialStatus(sample.status);
          setValues({
            product_type: sample.product_type,
            status: sample.status,
            sample_decision: sample.sample_decision ?? "pending",
            is_sample_requested: sample.is_sample_requested,
            requested_sample_quantity: sample.requested_sample_quantity ?? "",
            unit: sample.unit ?? "",
            request_date: toDatetimeLocalValue(new Date(sample.request_date)),
            property_values: sample.property_values ?? sample.requested_spec_json ?? {},
            notes: sample.notes ?? "",
          });
        }
      } catch (caughtError) {
        if (!isMounted) {
          return;
        }
        if (caughtError instanceof ApiClientError && caughtError.status === 404) {
          setIsNotFound(true);
          return;
        }
        setError(getApiErrorMessage(caughtError, messages));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadSample();
    return () => {
      isMounted = false;
    };
  }, [sampleId, messages]);

  function updateField<TField extends keyof SampleEditValues>(
    field: TField,
    value: SampleEditValues[TField],
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
      const payload: UpdateSampleRequest = {
        ...(specChanged ? { product_type: values.product_type, property_values: values.property_values } : {}),
        sample_decision: values.sample_decision,
        is_sample_requested: values.is_sample_requested,
        requested_sample_quantity: values.is_sample_requested
          ? Number(values.requested_sample_quantity)
          : null,
        unit: values.is_sample_requested ? optionalText(values.unit) : null,
        request_date: new Date(values.request_date).toISOString(),
        notes: optionalText(values.notes) ?? null,
      };

      if (values.status !== initialStatus) {
        payload.status = values.status;
      }

      await updateSample(sampleId, payload);
      setSuccessRedirect(`/samples/${sampleId}`);
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
        message={t("updateSuccess")}
        okLabel={common("actions.ok")}
        onOk={() => router.replace(successRedirect)}
      />
    ) : null}
    <PageFrame
      title={t("editTitle")}
      subtitle={sampleCode ?? t("detailSubtitle")}
      action={
        <Link href={`/samples/${sampleId}`} style={sharedStyles.secondaryButton}>
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
          <Link href="/samples" style={sharedStyles.button}>
            {t("backToList")}
          </Link>
        </section>
      ) : null}

      {!isLoading && !isNotFound ? (
        <section style={styles.panel}>
          <form style={styles.form} onSubmit={handleSubmit}>
            <p style={styles.codeNote}>
              {t("fields.sampleCode")}: <strong>{sampleCode}</strong>
            </p>

            <div style={styles.formGrid}>

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
                  {sampleStatusEditOptions.filter(s => s === initialStatus || hasPermission(SAMPLE_STATUS_PERMISSION[s])).map((s) => (
                    <option
                      key={s}
                      value={s}
                      disabled={s === "evaluated" && values.status !== "evaluated"}
                    >
                      {getEnumLabel("sample", "status", s, tEnums)}
                    </option>
                  ))}
                </select>
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.sampleDecision")}</span>
                <select
                  style={sharedStyles.input}
                  value={values.sample_decision}
                  onChange={(event) =>
                    updateField("sample_decision", event.target.value as SampleDecision)
                  }
                  disabled={isSubmitting || !hasPermission('commercial:samples:decide')}
                >
                  {sampleDecisionOptions.map((d) => (
                    <option key={d} value={d}>
                      {getEnumLabel("sample", "decision", d, tEnums)}
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
          <SampleProductFields productKey={values.product_type} values={values.property_values} original={productDefinition} unchanged={!specChanged} disabled={isSubmitting} onReady={setSpecReady}
            onChange={(key, specs, unit) => { setSpecChanged(true); setValues(v => ({ ...v, product_type: key, property_values: specs, ...(unit !== undefined ? { unit: unit ?? "" } : {}) })); }} />


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
                {isSubmitting ? messages("loading.saving") : t("updateButton")}
              </button>
              <Link href={`/samples/${sampleId}`} style={sharedStyles.secondaryButton}>
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
