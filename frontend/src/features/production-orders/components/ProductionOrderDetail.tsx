"use client";
import { SpecList } from "@/features/commercial-orders/components/sales-lifecycle";

import Link from "next/link";
import { OrderAllocations } from "./OrderAllocations";
import { OrderLines } from "./OrderLines";
import { OrderReportButton } from '@/features/reports/OrderReportButton';
import { OrderStatusPanel } from "./OrderStatusPanel";
import {Tabs} from "@/components/ui/Tabs";
import {RecordHistory} from "@/components/RecordHistory";
import { OrderStatusTimeline } from "./OrderStatusTimeline";
import {RescheduleOrderButton} from "./OrderReschedule";
import { OrderResultSection } from "@/features/production-results";
import { OrderWasteSection } from "@/features/waste-records";
import { OrderDowntimeSection } from "@/features/downtime-events";
import { OrderQualitySection } from "@/features/order-quality";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

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
import { useProductName } from "@/features/masterdata";
import { Signatures } from "@/components/Signatures";

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
  codeBlock: {
    background: "var(--surface-muted)",
    border: "1px solid var(--border)",
    borderRadius: "6px",
    margin: 0,
    overflowX: "auto",
    padding: "12px",
    whiteSpace: "pre-wrap",
  },
};

export function ProductionOrderDetail() {
  const history=useTranslations("production.recordHistory");
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
  const productName = useProductName();  // MD-001: the product's name, not its key
  const [created, setCreated] = useState(false);
  const [revision, setRevision] = useState(0);
  const loadedOrderId=useRef<string|null>(null);
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
        setIsLoading(loadedOrderId.current!==productionOrderId);
        setError(null);
        setIsNotFound(false);
        const orderResponse = await getProductionOrderById(productionOrderId);

        if (isMounted) {
          setOrder(orderResponse);
          loadedOrderId.current=productionOrderId;
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
      subtitle={order ? productName(order.product_type) : t("detailSubtitle")}
      action={
        <Link href="/production-orders" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      {created && <p role="status">{allocationText("success")}</p>}
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
        <Tabs label={t("detailTitle")} items={[{id:"data",label:history("data"),content:<>
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
            <DetailItem label={t("fields.productType")} value={productName(order.product_type)} />
            <DetailItem
              label={t("fields.plannedQuantity")}
              value={fmt.quantity(order.planned_quantity, order.unit)}
            />
            <DetailItem label={t("fields.plannedStartDate")} value={fmt.date(order.planned_start_date)} />
            <DetailItem label={t("fields.plannedEndDate")} value={<>{fmt.date(order.planned_end_date)} <RescheduleOrderButton order={order} onChanged={()=>setRevision(value=>value+1)}/></>} />
            <DetailItem
              label={t("fields.workCenter")}
              value={
                <Link href={`/work-centers/${order.work_center_id}`} style={{ color: "var(--accent-strong)" }}>
                  {workCenter ? `${workCenter.code} - ${workCenter.name}` : order.work_center_id}
                </Link>
              }
            />
            <DetailItem label={t("fields.notes")} value={order.notes} />
          </section>

          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>{t("specificationsSection")}</h2>
            {order.target_spec_json && Object.keys(order.target_spec_json).length > 0 ? (
              <SpecList productKey={order.product_type ?? ""} spec={order.target_spec_json} />
            ) : (
              <p style={{ margin: 0 }}>{t("noSpecifications")}</p>
            )}
          </section>

          <OrderStatusPanel order={order} onChanged={() => setRevision((value) => value + 1)} />
          <OrderReportButton orderId={order.id}/>
          <OrderLines order={order} onChanged={() => setRevision((value) => value + 1)} />
          <OrderResultSection order={order} revision={revision} />
          <OrderWasteSection order={order} revision={revision} />
          <OrderDowntimeSection order={order} revision={revision} />
          <OrderQualitySection order={order} revision={revision} />
          <OrderAllocations order={order} />
          {/* Planning orders show their lines above; manual items remain for orders without allocations. */}
          {order.allocations.length === 0 && (
            <ProductionOrderItemsList
              productType={order.product_type ?? undefined}
              productionOrderId={order.id}
              productionOrderStatus={order.status}
            />
          )}
        </>},{id:"history",label:history("title"),content:<><RecordHistory entityType="production_order" entityId={order.id} revision={revision}/><details><summary>{history("legacyTimeline")}</summary><OrderStatusTimeline orderId={order.id} revision={revision} reschedules={order.reschedule_history}/></details></>}]} />
      ) : null}
          {order && <Signatures resourceType="production_order" id={order.id} version={order.status} />}
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
