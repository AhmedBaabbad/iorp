"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getProductionOrders } from "@/features/production-orders";
import { getShifts } from "@/features/shifts";
import { getWorkCenters } from "@/features/work-centers";
import { useFormatter } from "@/hooks/useFormatter";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import {
  getShiftReportById,
  updateShiftReportStatus,
} from "../api/shift-reports-api";
import type { ShiftReportData, ShiftReportStatus } from "../types";
import { ShiftReportStatusBadge } from "./ShiftReportStatusBadge";

type WorkCenterOption = {
  id: string;
  code: string;
  name: string;
};

type ShiftOption = {
  id: string;
  code: string;
  name: string;
  shift_type: string;
};

type ProductionOrderOption = {
  id: string;
  production_order_number: string;
  product_type: string;
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
  actions: {
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
    marginBottom: "18px",
  },
};

export function ShiftReportDetail() {
  const t = useTranslations("production.shiftReports");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const params = useParams<{ id: string }>();
  const shiftReportId = params.id;
  const [report, setReport] = useState<ShiftReportData | null>(null);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [shifts, setShifts] = useState<ShiftOption[]>([]);
  const [productionOrders, setProductionOrders] = useState<ProductionOrderOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadShiftReport() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);

        const reportResponse = await getShiftReportById(shiftReportId);

        if (isMounted) {
          setReport(reportResponse);
        }

        const [
          workCentersResponse,
          shiftsResponse,
          productionOrdersResponse,
        ] = await Promise.all([
          getWorkCenters().catch(() => []),
          getShifts().catch(() => []),
          getProductionOrders().catch(() => []),
        ]);

        if (isMounted) {
          setWorkCenters(workCentersResponse);
          setShifts(shiftsResponse);
          setProductionOrders(productionOrdersResponse);
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

    void loadShiftReport();

    return () => {
      isMounted = false;
    };
  }, [shiftReportId, t]);

  async function handleStatusAction(nextStatus: ShiftReportStatus) {
    setStatusError(null);
    setIsUpdatingStatus(true);

    try {
      const updatedReport = await updateShiftReportStatus(shiftReportId, nextStatus);
      if (isMountedRef.current) {
        setReport(updatedReport);
      }
    } catch (caughtError) {
      if (isMountedRef.current) {
        setStatusError(getApiErrorMessage(caughtError, messages));
      }
    } finally {
      if (isMountedRef.current) {
        setIsUpdatingStatus(false);
      }
    }
  }

  const workCenter = report
    ? workCenters.find((item) => item.id === report.work_center_id)
    : undefined;
  const shift = report
    ? shifts.find((item) => item.id === report.shift_definition_id)
    : undefined;
  const productionOrder = report?.production_order_id
    ? productionOrders.find((item) => item.id === report.production_order_id)
    : undefined;

  return (
    <PageFrame
      section="Production"
      title={report ? `${t("detailTitle")} ${fmt.date(report.report_date)}` : t("detailTitle")}
      subtitle={report ? report.summary : t("detailSubtitle")}
      action={
        <Link href="/shift-reports" style={sharedStyles.secondaryButton}>
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
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
          <p style={{ margin: "0 0 18px" }}>
            {t("notFoundDescription")}
          </p>
          <Link href="/shift-reports" style={sharedStyles.button}>
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
            {report.status === "draft" ? (
              <button
                style={sharedStyles.button}
                type="button"
                disabled={isUpdatingStatus}
                onClick={() => void handleStatusAction("submitted")}
              >
                {isUpdatingStatus ? t("actions.submitting") : t("actions.submit")}
              </button>
            ) : null}

            {report.status === "submitted" ? (
              <button
                style={sharedStyles.button}
                type="button"
                disabled={isUpdatingStatus}
                onClick={() => void handleStatusAction("approved")}
              >
                {isUpdatingStatus ? t("actions.approving") : t("actions.approve")}
              </button>
            ) : null}

            {report.status === "approved" ? (
              <div style={sharedStyles.state}>{t("approvedFinalMessage")}</div>
            ) : null}
          </div>

          {statusError ? (
            <div style={{ ...sharedStyles.error, marginBottom: "18px" }} role="alert">
              {statusError}
            </div>
          ) : null}

          <section style={styles.detailGrid} aria-label={t("detailTitle")}>
            <DetailItem label={t("fields.reportDate")} value={fmt.date(report.report_date)} />
            <DetailItem
              label={t("fields.status")}
              value={<ShiftReportStatusBadge status={report.status} />}
            />
            <DetailItem label={t("fields.summary")} value={report.summary} />
            <DetailItem label={t("fields.shiftStartTime")} value={fmt.dateTime(report.shift_started_at)} />
            <DetailItem label={t("fields.shiftEndTime")} value={fmt.dateTime(report.shift_ended_at)} />
            <DetailItem
              label={t("fields.workCenter")}
              value={
                <Link href={`/work-centers/${report.work_center_id}`} style={{ color: "#1d4ed8" }}>
                  {workCenter ? `${workCenter.code} - ${workCenter.name}` : report.work_center_id}
                </Link>
              }
            />
            <DetailItem
              label={t("fields.shift")}
              value={
                <Link href={`/shifts/${report.shift_definition_id}`} style={{ color: "#1d4ed8" }}>
                  {shift ? `${shift.code} - ${shift.name}` : report.shift_definition_id}
                </Link>
              }
            />
            <DetailItem
              label={t("fields.productionOrder")}
              value={
                report.production_order_id ? (
                  <Link
                    href={`/production-orders/${report.production_order_id}`}
                    style={{ color: "#1d4ed8" }}
                  >
                    {productionOrder
                      ? `${productionOrder.production_order_number} - ${productionOrder.product_type}`
                      : report.production_order_id}
                  </Link>
                ) : null
              }
            />
            <DetailItem label={t("fields.notes")} value={report.notes} />
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
