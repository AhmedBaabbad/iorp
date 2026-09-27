"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getCustomer } from "@/features/customers";
import { SampleEvaluationsList } from "@/features/sample-evaluations";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { ApiClientError } from "@/lib/api-client";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { getSampleById } from "../api/samples-api";
import type { SampleData } from "../types";
import { SampleDecisionBadge } from "./SampleDecisionBadge";
import { SampleStatusBadge } from "./SampleStatusBadge";

const styles: Record<string, CSSProperties> = {
  detailGrid: {
    display: "grid",
    gap: "1px",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    background: "#e4e7ec",
    borderRadius: "8px",
    overflow: "hidden",
  },
  detailItem: {
    background: "#ffffff",
    padding: "18px",
  },
  detailLabel: {
    color: "#52606d",
    fontSize: "13px",
    fontWeight: 700,
    margin: "0 0 8px",
  },
  detailValue: {
    margin: 0,
    overflowWrap: "anywhere",
  },
  specBlock: {
    background: "#111827",
    borderRadius: "8px",
    color: "#f9fafb",
    fontSize: "13px",
    margin: 0,
    overflowX: "auto",
    padding: "16px",
    whiteSpace: "pre-wrap",
  },
  sections: {
    display: "grid",
    gap: "24px",
  },
};

type SampleDetailProps = {
  sampleId: string;
};

export function SampleDetail({ sampleId }: SampleDetailProps) {
  const messages = useTranslations("messages");
  const t = useTranslations("commercial.samples");
  const fmt = useFormatter();
  const [sample, setSample] = useState<SampleData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [customerName, setCustomerName] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadSample() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const response = await getSampleById(sampleId);

        if (isMounted) {
          setSample(response);
        }

        try {
          const customer = await getCustomer(response.customer_id);
          if (isMounted) {
            setCustomerName(customer.name);
          }
        } catch {
          // Non-critical: the customer UUID fallback is already shown.
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
  }, [sampleId]);

  return (
    <PageFrame
      title={sample?.sample_code ?? t("detailTitle")}
      subtitle={sample ? sample.product_type : t("detailSubtitle")}
      action={
        <Link href="/samples" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "#ffffff" }}>{messages("loading.default")}</div>
      ) : null}

      {!isLoading && isNotFound ? (
        <section style={{ ...sharedStyles.state, background: "#ffffff" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
          <p style={{ margin: "0 0 18px" }}>{t("notFoundDescription")}</p>
          <Link href="/samples" style={sharedStyles.button}>
            {t("returnToList")}
          </Link>
        </section>
      ) : null}

      {!isLoading && error ? (
        <div style={sharedStyles.error} role="alert">
          {error}
        </div>
      ) : null}

      {!isLoading && !error && !isNotFound && sample ? (
        <div style={styles.sections}>
          <section style={styles.detailGrid} aria-label={t("detailsAria")}>
            <DetailItem label={t("fields.sampleCode")} value={sample.sample_code} />
            <DetailItem
              label={t("fields.customer")}
              value={
                <Link href={`/customers/${sample.customer_id}`} style={{ color: "#1d4ed8" }}>
                  {customerName ?? sample.customer_id}
                </Link>
              }
            />
            <DetailItem label={t("fields.productType")} value={sample.product_type} />
            <DetailItem
              label={t("fields.status")}
              value={<SampleStatusBadge status={sample.status} />}
            />
            <DetailItem
              label={t("fields.sampleDecision")}
              value={<SampleDecisionBadge decision={sample.sample_decision} />}
            />
            <DetailItem
              label={t("fields.sampleRequested")}
              value={sample.is_sample_requested ? t("labels.yes") : t("labels.no")}
            />
            <DetailItem
              label={t("fields.requestedSampleQuantity")}
              value={
                sample.is_sample_requested
                  ? fmt.quantity(sample.requested_sample_quantity, sample.unit)
                  : null
              }
            />
            <DetailItem label={t("fields.requestDate")} value={fmt.dateTime(sample.request_date)} />
            <DetailItem label={t("fields.created")} value={fmt.dateTime(sample.created_at)} />
            <DetailItem label={t("fields.updated")} value={fmt.dateTime(sample.updated_at)} />
            <DetailItem label={t("fields.notes")} value={sample.notes} />
          </section>

          <section aria-label={t("sections.requestedSpecifications")}>
            <h2 style={{ fontSize: "18px", margin: "0 0 12px" }}>{t("sections.requestedSpecifications")}</h2>
            <pre style={styles.specBlock}>
              {sample.requested_spec_json
                ? JSON.stringify(sample.requested_spec_json, null, 2)
                : t("labels.noRequestedSpecifications")}
            </pre>
          </section>

          <SampleEvaluationsList sampleId={sampleId} />
        </div>
      ) : null}
    </PageFrame>
  );
}

function DetailItem({
  label,
  value,
}: {
  label: string;
  value: string | number | null | ReactNode;
}) {
  return (
    <div style={styles.detailItem}>
      <p style={styles.detailLabel}>{label}</p>
      <p style={styles.detailValue}>
        {typeof value === "string" || typeof value === "number" || value === null
          ? displayValue(value)
          : value}
      </p>
    </div>
  );
}
