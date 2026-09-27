"use client";

import Link from "next/link";
import { OrderAllocations } from "./OrderAllocations";
import { ExecutionPanel } from "@/features/production-execution/ExecutionPanel";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { ProductionOrderItemsList } from "@/features/production-order-items";
import { getWorkCenters } from "@/features/work-centers";
import { useFormatter } from "@/hooks/useFormatter";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { getProductionOrderById } from "../api/production-orders-api";
import type { ProductionOrderData } from "../types";
import { ProductionOrderPriorityBadge } from "./ProductionOrderPriorityBadge";
import { ProductionOrderStatusBadge } from "./ProductionOrderStatusBadge";

type WorkCenterOption = {
  id: string;
  code: string;
  name: string;
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
  codeBlock: {
    background: "#f8fafc",
    border: "1px solid #e4e7ec",
    borderRadius: "6px",
    margin: 0,
    overflowX: "auto",
    padding: "12px",
    whiteSpace: "pre-wrap",
  },
};

export function ProductionOrderDetail() {
  const t = useTranslations("production.productionOrders");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const params = useParams<{ id: string }>();
  const productionOrderId = params.id;
  const [order, setOrder] = useState<ProductionOrderData | null>(null);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const allocationText = useTranslations("production.allocation");
  const [created, setCreated] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (sessionStorage.getItem("production-order-created") === productionOrderId) {
      setCreated(true);
      sessionStorage.removeItem("production-order-created");
    }
  }, [productionOrderId]);

  useEffect(() => {
    let isMounted = true;

    async function loadProductionOrder() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const orderResponse = await getProductionOrderById(productionOrderId);

        if (isMounted) {
          setOrder(orderResponse);
        }

        const workCentersResponse = await getWorkCenters().catch(() => []);

        if (isMounted) {
          setWorkCenters(workCentersResponse);
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

    void loadProductionOrder();

    return () => {
      isMounted = false;
    };
  }, [productionOrderId, t, messages, revision]);

  const workCenter = order
    ? workCenters.find((item) => item.id === order.work_center_id)
    : undefined;

  return (
    <PageFrame
      title={order?.production_order_number ?? t("detailTitle")}
      subtitle={order ? order.product_type : t("detailSubtitle")}
      action={
        <Link href="/production-orders" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      {created && <p role="status">{allocationText("success")}</p>}
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
          <Link href="/production-orders" style={sharedStyles.button}>
            {t("returnToList")}
          </Link>
        </section>
      ) : null}

      {!isLoading && error ? (
        <div style={sharedStyles.error} role="alert">
          {error}
        </div>
      ) : null}

      {!isLoading && !error && !isNotFound && order ? (
        <>
          <section style={styles.detailGrid} aria-label={t("detailTitle")}>
            <DetailItem label={t("fields.orderNumber")} value={order.production_order_number} />
            <DetailItem
              label={t("fields.status")}
              value={<ProductionOrderStatusBadge status={order.status} />}
            />
            <DetailItem
              label={t("fields.priority")}
              value={<ProductionOrderPriorityBadge priority={order.priority} />}
            />
            <DetailItem label={t("fields.productType")} value={order.product_type} />
            <DetailItem
              label={t("fields.plannedQuantity")}
              value={fmt.quantity(order.planned_quantity, order.unit)}
            />
            <DetailItem label={t("fields.plannedStartDate")} value={fmt.date(order.planned_start_date)} />
            <DetailItem label={t("fields.plannedEndDate")} value={fmt.date(order.planned_end_date)} />
            <DetailItem
              label={t("fields.workCenter")}
              value={
                <Link href={`/work-centers/${order.work_center_id}`} style={{ color: "#1d4ed8" }}>
                  {workCenter ? `${workCenter.code} - ${workCenter.name}` : order.work_center_id}
                </Link>
              }
            />
            <DetailItem label={t("fields.notes")} value={order.notes} />
          </section>

          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>{t("specificationsSection")}</h2>
            {order.target_spec_json && Object.keys(order.target_spec_json).length > 0 ? (
              <pre style={styles.codeBlock}>
                {JSON.stringify(order.target_spec_json, null, 2)}
              </pre>
            ) : (
              <p style={{ margin: 0 }}>{t("noSpecifications")}</p>
            )}
          </section>

          <OrderAllocations order={order} onChanged={() => setRevision((value) => value + 1)} />
          <ExecutionPanel orderId={order.id} />
          <ProductionOrderItemsList
            productionOrderId={order.id}
            productionOrderStatus={order.status}
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
