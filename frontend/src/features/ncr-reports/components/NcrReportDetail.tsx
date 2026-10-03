"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";

import { usePermission } from "@/features/auth/permission-hooks";
import { Q } from "@/lib/quality-permissions";
import { PageFrame } from "@/components/layout/page-frame";
import { NcrItemsList } from "@/features/ncr-items";
import { useFormatter } from "@/hooks/useFormatter";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import {
  getNcrReportById,
  updateNcrReportStatus,
} from "../api/ncr-reports-api";
import type { NCRStatus, NcrReportData } from "../types";
import { NcrSourceTypeBadge } from "./NcrSourceTypeBadge";
import { NcrStatusBadge } from "./NcrStatusBadge";
import {
  formatReportType,
  shortId,
} from "./ncr-report-utils";

type NcrReportDetailProps = {
  ncrReportId: string;
};

const styles: Record<string, CSSProperties> = {
  detailGrid: {
    display: "grid",
    gap: "1px",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    background: "var(--border)",
    borderRadius: "8px",
    overflow: "hidden",
  },
  detailItem: {
    background: "var(--surface)",
    padding: "18px",
  },
  detailLabel: {
    color: "var(--text-muted)",
    fontSize: "13px",
    fontWeight: 700,
    margin: "0 0 8px",
  },
  detailValue: {
    margin: 0,
    overflowWrap: "anywhere",
  },
  section: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
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
  description: {
    background: "var(--surface-muted)",
    border: "1px solid var(--border)",
    borderRadius: "6px",
    lineHeight: 1.55,
    margin: 0,
    padding: "14px",
    whiteSpace: "pre-wrap",
  },
};

export function NcrReportDetail({ ncrReportId }: NcrReportDetailProps) {
  const t = useTranslations("ncr.ncrReports");
  const canUpdate = usePermission(Q.NCR_UPDATE);
  const tEnums = useTranslations();
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [report, setReport] = useState<NcrReportData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadReport() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const response = await getNcrReportById(ncrReportId);

        if (isMounted) {
          setReport(response);
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

    void loadReport();

    return () => {
      isMounted = false;
    };
  }, [ncrReportId, t]);

  async function handleStatusAction(nextStatus: NCRStatus) {
    setActionError(null);
    setIsUpdating(true);

    try {
      const updatedReport = await updateNcrReportStatus(ncrReportId, {
        status: nextStatus,
      });
      setReport(updatedReport);
    } catch (caughtError) {
      setActionError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsUpdating(false);
    }
  }

  return (
    <PageFrame
      section="Quality"
      title={report?.report_number ?? t("detailTitle")}
      subtitle={report ? report.title : t("detailSubtitle")}
      action={
        <Link href="/non-conformance-reports" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          {t("loadingDetail")}
        </div>
      ) : null}

      {!isLoading && isNotFound ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>
            {t("notFound")}
          </h2>
          <p style={{ margin: "0 0 18px" }}>
            {t("notFoundDescription")}
          </p>
          <Link href="/non-conformance-reports" style={sharedStyles.button}>
            {t("returnToList")}
          </Link>
        </section>
      ) : null}

      {!isLoading && error ? (
        <div style={sharedStyles.error} role="alert">
          {error}
        </div>
      ) : null}

      {!isLoading && !error && !isNotFound && report ? (
        <>
          <div style={styles.actions}>
            {canUpdate && report.status === "draft" ? (
              <button
                style={sharedStyles.button}
                type="button"
                disabled={isUpdating}
                onClick={() => void handleStatusAction("open")}
              >
                {isUpdating ? t("actions.opening") : t("actions.openReport")}
              </button>
            ) : null}

            {canUpdate && report.status === "open" ? (
              <button
                style={sharedStyles.button}
                type="button"
                disabled={isUpdating}
                onClick={() => void handleStatusAction("under_review")}
              >
                {isUpdating ? t("actions.startingReview") : t("actions.startReview")}
              </button>
            ) : null}

            {canUpdate && report.status === "under_review" ? (
              <button
                style={sharedStyles.button}
                type="button"
                disabled={isUpdating}
                onClick={() => void handleStatusAction("closed")}
              >
                {isUpdating ? t("actions.closing") : t("actions.closeReport")}
              </button>
            ) : null}

            {report.status === "closed" ? (
              <div style={sharedStyles.state}>{t("closedMessage")}</div>
            ) : null}
          </div>

          {actionError ? (
            <div style={{ ...sharedStyles.error, marginBottom: "18px" }} role="alert">
              {actionError}
            </div>
          ) : null}

          <section style={styles.detailGrid} aria-label={t("detailTitle")}>
            <DetailItem label={t("fields.reportNumber")} value={report.report_number} />
            <DetailItem label={t("fields.reportDate")} value={fmt.date(report.report_date)} />
            <DetailItem
              label={t("fields.sourceType")}
              value={<NcrSourceTypeBadge sourceType={report.source_type} />}
            />
            <DetailItem label={t("fields.reportType")} value={formatReportType(report.report_type, tEnums)} />
            <DetailItem label={t("fields.status")} value={<NcrStatusBadge status={report.status} />} />
            <DetailItem label={t("fields.referenceCode")} value={report.reference_code} />
            <DetailItem label={t("fields.title")} value={report.title} />
          </section>

          <section style={styles.section} aria-label={t("descriptionSection")}>
            <h2 style={styles.sectionTitle}>{t("descriptionSection")}</h2>
            <p style={styles.description}>{report.description}</p>
          </section>

          <section style={styles.section} aria-label={t("qualityChainSection")}>
            <h2 style={styles.sectionTitle}>{t("qualityChainSection")}</h2>
            <section style={styles.detailGrid}>
              <DetailItem
                label={t("fields.qualityCheck")}
                value={
                  report.quality_check_id ? (
                    <Link
                      href={`/quality-checks/${report.quality_check_id}`}
                      style={{ color: "var(--accent-strong)" }}
                    >
                      {shortId(report.quality_check_id)}
                    </Link>
                  ) : null
                }
              />
              <DetailItem
                label={t("fields.qualityRejection")}
                value={
                  report.quality_rejection_id ? (
                    <Link
                      href={`/quality-rejections/${report.quality_rejection_id}`}
                      style={{ color: "var(--accent-strong)" }}
                    >
                      {shortId(report.quality_rejection_id)}
                    </Link>
                  ) : null
                }
              />
            </section>
          </section>

          <NcrItemsList ncrReportId={report.id} reportStatus={report.status} />
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
