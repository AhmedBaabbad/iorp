"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { QualityDefectsList } from "@/features/quality-defects";
import { getItemsByOrder } from "@/features/production-order-items";
import type { ProductionOrderItemListItem } from "@/features/production-order-items";
import { getProductionOrders } from "@/features/production-orders";
import { useFormatter } from "@/hooks/useFormatter";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import {
  getQualityCheckById,
  updateQualityCheckStatus,
} from "../api/quality-checks-api";
import type {
  QualityCheckData,
  QualityCheckResult,
} from "../types";
import { QualityCheckResultBadge } from "./QualityCheckResultBadge";
import { QualityCheckStatusBadge } from "./QualityCheckStatusBadge";
import {
  formatCheckType,
  shortId,
} from "./quality-check-utils";

type QualityCheckDetailProps = {
  qualityCheckId: string;
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
    alignItems: "end",
    marginBottom: "18px",
  },
};

export function QualityCheckDetail({ qualityCheckId }: QualityCheckDetailProps) {
  const t = useTranslations("quality.qualityChecks");
  const tEnums = useTranslations();
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [check, setCheck] = useState<QualityCheckData | null>(null);
  const [productionOrders, setProductionOrders] = useState<ProductionOrderOption[]>([]);
  const [orderItems, setOrderItems] = useState<ProductionOrderItemListItem[]>([]);
  const [selectedResult, setSelectedResult] = useState<"" | QualityCheckResult>("");
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadQualityCheck() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);

        const checkResponse = await getQualityCheckById(qualityCheckId);

        if (isMounted) {
          setCheck(checkResponse);
          setSelectedResult(checkResponse.result ?? "");
        }

        const productionOrdersPromise = getProductionOrders().catch(() => []);
        const orderItemsPromise = checkResponse.production_order_id
          ? getItemsByOrder(checkResponse.production_order_id).catch(() => [])
          : Promise.resolve([]);

        const [
          productionOrdersResponse,
          orderItemsResponse,
        ] = await Promise.all([
          productionOrdersPromise,
          orderItemsPromise,
        ]);

        if (isMounted) {
          setProductionOrders(productionOrdersResponse);
          setOrderItems(orderItemsResponse);
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

    void loadQualityCheck();

    return () => {
      isMounted = false;
    };
  }, [qualityCheckId, t]);

  async function handleStartInspection() {
    setStatusError(null);
    setIsUpdatingStatus(true);

    try {
      const updatedCheck = await updateQualityCheckStatus(qualityCheckId, {
        status: "under_inspection",
      });
      setCheck(updatedCheck);
      setSelectedResult(updatedCheck.result ?? "");
    } catch (caughtError) {
      setStatusError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsUpdatingStatus(false);
    }
  }

  async function handleCloseInspection() {
    if (!selectedResult) {
      return;
    }

    setStatusError(null);
    setIsUpdatingStatus(true);

    try {
      const updatedCheck = await updateQualityCheckStatus(qualityCheckId, {
        status: "closed",
        result: selectedResult,
      });
      setCheck(updatedCheck);
      setSelectedResult(updatedCheck.result ?? "");
    } catch (caughtError) {
      setStatusError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsUpdatingStatus(false);
    }
  }

  const productionOrder = check?.production_order_id
    ? productionOrders.find((item) => item.id === check.production_order_id)
    : undefined;
  const orderItem = check?.production_order_item_id
    ? orderItems.find((item) => item.id === check.production_order_item_id)
    : undefined;

  return (
    <PageFrame
      section="Quality"
      title={check?.inspection_code ?? t("detailTitle")}
      subtitle={check ? formatCheckType(check.check_type, tEnums) : t("detailSubtitle")}
      action={
        <Link href="/quality-checks" style={sharedStyles.secondaryButton}>
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
          <Link href="/quality-checks" style={sharedStyles.button}>
            {t("returnToList")}
          </Link>
        </section>
      ) : null}

      {!isLoading && error ? (
        <div style={sharedStyles.error} role="alert">
          {error}
        </div>
      ) : null}

      {!isLoading && !error && !isNotFound && check ? (
        <>
          <div style={styles.actions}>
            {check.status === "open" ? (
              <button
                style={sharedStyles.button}
                type="button"
                disabled={isUpdatingStatus}
                onClick={() => void handleStartInspection()}
              >
                {isUpdatingStatus ? t("actions.startingInspection") : t("actions.startInspection")}
              </button>
            ) : null}

            {check.status === "under_inspection" ? (
              <>
                <label style={{ ...sharedStyles.field, minWidth: "260px" }}>
                  <span style={sharedStyles.label}>{t("fields.result")}</span>
                  <select
                    style={sharedStyles.input}
                    value={selectedResult}
                    onChange={(event) =>
                      setSelectedResult(event.target.value as "" | QualityCheckResult)
                    }
                    disabled={isUpdatingStatus}
                  >
                    <option value="">{t("selectResult")}</option>
                    <option value="accepted">Accepted</option>
                    <option value="rejected">Rejected</option>
                    <option value="conditional_accept">Conditional Accept</option>
                    <option value="needs_reinspection">Needs Reinspection</option>
                  </select>
                </label>
                <button
                  style={sharedStyles.button}
                  type="button"
                  disabled={isUpdatingStatus || !selectedResult}
                  title={!selectedResult ? t("actions.closeRequiresResult") : undefined}
                  onClick={() => void handleCloseInspection()}
                >
                  {isUpdatingStatus ? t("actions.closingInspection") : t("actions.closeInspection")}
                </button>
              </>
            ) : null}

            {check.status === "closed" ? (
              <div style={sharedStyles.state}>{t("closedMessage")}</div>
            ) : null}
          </div>

          {statusError ? (
            <div style={{ ...sharedStyles.error, marginBottom: "18px" }} role="alert">
              {statusError}
            </div>
          ) : null}

          <section style={styles.detailGrid} aria-label={t("detailTitle")}>
            <DetailItem label={t("fields.inspectionCode")} value={check.inspection_code} />
            <DetailItem label={t("fields.checkDate")} value={fmt.dateTime(check.check_datetime)} />
            <DetailItem
              label={t("fields.checkType")}
              value={
                <span style={checkTypeBadgeStyle}>
                  {formatCheckType(check.check_type, tEnums)}
                </span>
              }
            />
            <DetailItem
              label={t("fields.status")}
              value={<QualityCheckStatusBadge status={check.status} />}
            />
            <DetailItem
              label={t("fields.result")}
              value={<QualityCheckResultBadge result={check.result} />}
            />
            <DetailItem label={t("fields.notes")} value={check.notes} />
          </section>

          <section style={styles.section} aria-label={t("quantitySection")}>
            <h2 style={styles.sectionTitle}>{t("quantitySection")}</h2>
            <section style={styles.detailGrid}>
              <DetailItem label={t("fields.qtyInspected")} value={fmt.number(check.qty_inspected)} />
              <DetailItem label={t("fields.qtyAccepted")} value={fmt.number(check.qty_accepted)} />
              <DetailItem label={t("fields.qtyRejected")} value={fmt.number(check.qty_rejected)} />
            </section>
          </section>

          <section style={styles.section} aria-label={t("productionContextSection")}>
            <h2 style={styles.sectionTitle}>{t("productionContextSection")}</h2>
            <section style={styles.detailGrid}>
              <DetailItem
                label={t("fields.productionOrder")}
                value={
                  check.production_order_id ? (
                    <Link
                      href={`/production-orders/${check.production_order_id}`}
                      style={{ color: "var(--accent-strong)" }}
                    >
                      {productionOrder
                        ? `${productionOrder.production_order_number} - ${productionOrder.product_type}`
                        : shortId(check.production_order_id)}
                    </Link>
                  ) : null
                }
              />
              <DetailItem
                label={t("fields.productionOrderItem")}
                value={
                  check.production_order_item_id
                    ? orderItem
                      ? `Line ${orderItem.line_no}`
                      : shortId(check.production_order_item_id)
                    : null
                }
              />
            </section>
          </section>

          <QualityDefectsList
            qualityCheckId={check.id}
            checkStatus={check.status}
          />
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

const checkTypeBadgeStyle: CSSProperties = {
  ...sharedStyles.badge,
  background: "var(--accent-soft)",
  color: "var(--accent-strong)",
};
