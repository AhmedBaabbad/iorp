"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { useFormatter } from "@/hooks/useFormatter";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import {
  getQualityRejectionById,
  updateDispositionStatus,
} from "../api/quality-rejections-api";
import type { QualityRejectionData } from "../types";
import { DispositionBadge } from "./DispositionBadge";
import { DispositionStatusBadge } from "./DispositionStatusBadge";
import { formatRejectionReason, shortId } from "./quality-rejection-utils";

type QualityRejectionDetailProps = {
  rejectionId: string;
};

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
  section: {
    background: "#ffffff",
    border: "1px solid #d9dee7",
    borderRadius: "8px",
    marginTop: "18px",
    padding: "18px",
  },
  sectionTitle: {
    fontSize: "18px",
    margin: "0 0 12px",
  },
  actions: {
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
    marginBottom: "18px",
  },
  notes: {
    background: "#f8fafc",
    border: "1px solid #e4e7ec",
    borderRadius: "6px",
    lineHeight: 1.55,
    margin: 0,
    padding: "14px",
    whiteSpace: "pre-wrap",
  },
};

export function QualityRejectionDetail({ rejectionId }: QualityRejectionDetailProps) {
  const t = useTranslations("quality.qualityRejections");
  const tEnums = useTranslations();
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [rejection, setRejection] = useState<QualityRejectionData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadRejection() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const response = await getQualityRejectionById(rejectionId);

        if (isMounted) {
          setRejection(response);
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

    void loadRejection();

    return () => {
      isMounted = false;
    };
  }, [rejectionId, t]);

  async function handleMarkExecuted() {
    setActionError(null);
    setIsUpdating(true);

    try {
      const updatedRejection = await updateDispositionStatus(rejectionId);
      setRejection(updatedRejection);
    } catch (caughtError) {
      setActionError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsUpdating(false);
    }
  }

  return (
    <PageFrame
      section="Quality"
      title={rejection ? `${t("detailTitle")} ${fmt.date(rejection.rejection_date)}` : t("detailTitle")}
      subtitle={t("detailSubtitle")}
      action={
        <Link href="/quality-rejections" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "#ffffff" }}>
          {t("loadingDetail")}
        </div>
      ) : null}

      {!isLoading && isNotFound ? (
        <section style={{ ...sharedStyles.state, background: "#ffffff" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>
            {t("notFound")}
          </h2>
          <p style={{ margin: "0 0 18px" }}>
            {t("notFoundDescription")}
          </p>
          <Link href="/quality-rejections" style={sharedStyles.button}>
            {t("returnToList")}
          </Link>
        </section>
      ) : null}

      {!isLoading && error ? (
        <div style={sharedStyles.error} role="alert">
          {error}
        </div>
      ) : null}

      {!isLoading && !error && !isNotFound && rejection ? (
        <>
          <div style={styles.actions}>
            {rejection.disposition_status === "pending" ? (
              <button
                style={sharedStyles.button}
                type="button"
                disabled={isUpdating}
                onClick={() => void handleMarkExecuted()}
              >
                {isUpdating ? t("actions.marking") : t("actions.markAsExecuted")}
              </button>
            ) : (
              <div style={sharedStyles.state}>{t("executedMessage")}</div>
            )}
          </div>

          {actionError ? (
            <div style={{ ...sharedStyles.error, marginBottom: "18px" }} role="alert">
              {actionError}
            </div>
          ) : null}

          <section style={styles.detailGrid} aria-label={t("detailTitle")}>
            <DetailItem label={t("fields.rejectionDate")} value={fmt.date(rejection.rejection_date)} />
            <DetailItem
              label={t("fields.rejectionReason")}
              value={formatRejectionReason(rejection.rejection_reason, tEnums)}
            />
            <DetailItem
              label={t("fields.disposition")}
              value={<DispositionBadge disposition={rejection.disposition} />}
            />
            <DetailItem
              label={t("fields.dispositionStatus")}
              value={<DispositionStatusBadge status={rejection.disposition_status} />}
            />
            <DetailItem
              label={t("fields.quantityRejected")}
              value={fmt.quantity(rejection.quantity_rejected, rejection.unit)}
            />
          </section>

          <section style={styles.section} aria-label={t("rejectionJustificationSection")}>
            <h2 style={styles.sectionTitle}>{t("rejectionJustificationSection")}</h2>
            <p style={styles.notes}>{rejection.rejection_notes}</p>
          </section>

          <section style={styles.section} aria-label={t("qualityContextSection")}>
            <h2 style={styles.sectionTitle}>{t("qualityContextSection")}</h2>
            <section style={styles.detailGrid}>
              <DetailItem
                label={t("fields.qualityCheck")}
                value={
                  rejection.quality_check_id ? (
                    <Link
                      href={`/quality-checks/${rejection.quality_check_id}`}
                      style={{ color: "#1d4ed8" }}
                    >
                      {shortId(rejection.quality_check_id)}
                    </Link>
                  ) : null
                }
              />
              <DetailItem
                label={t("fields.qualityDefect")}
                value={
                  rejection.quality_defect_id ? (
                    rejection.quality_check_id ? (
                      <Link
                        href={`/quality-checks/${rejection.quality_check_id}`}
                        style={{ color: "#1d4ed8" }}
                      >
                        {shortId(rejection.quality_defect_id)}
                      </Link>
                    ) : (
                      shortId(rejection.quality_defect_id)
                    )
                  ) : null
                }
              />
            </section>
          </section>

          <section style={styles.section} aria-label={t("productionContextSection")}>
            <h2 style={styles.sectionTitle}>{t("productionContextSection")}</h2>
            <section style={styles.detailGrid}>
              <DetailItem
                label={t("fields.productionOutput")}
                value={
                  rejection.production_output_id ? (
                    <Link
                      href={`/production-outputs/${rejection.production_output_id}`}
                      style={{ color: "#1d4ed8" }}
                    >
                      {shortId(rejection.production_output_id)}
                    </Link>
                  ) : null
                }
              />
              <DetailItem
                label={t("fields.productionOrderItem")}
                value={
                  rejection.production_order_item_id
                    ? shortId(rejection.production_order_item_id)
                    : null
                }
              />
            </section>
          </section>
        </>
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
