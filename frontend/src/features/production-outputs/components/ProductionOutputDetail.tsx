"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getItemsByOrder } from "@/features/production-order-items";
import type { ProductionOrderItemListItem } from "@/features/production-order-items";
import { getProductionOrders } from "@/features/production-orders";
import { getShiftReportById } from "@/features/shift-reports";
import { getWorkCenters } from "@/features/work-centers";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getProductionOutputById } from "../api/production-outputs-api";
import type { ProductionOutputData } from "../types";
import { ProductionOutputStatusBadge } from "./ProductionOutputStatusBadge";
import {
  formatProductionOrderLabel,
  formatWorkCenterLabel,
  type ProductionOrderOption,
  type WorkCenterOption,
} from "./production-output-utils";

type ProductionOutputDetailProps = {
  productionOutputId: string;
};

type ShiftReportReference = {
  id: string;
  report_date: string;
};

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
    padding: "24px",
  },
  grid: {
    display: "grid",
    gap: "18px",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  },
  label: {
    color: "var(--text-muted)",
    display: "block",
    fontSize: "13px",
    marginBottom: "6px",
  },
  value: {
    color: "var(--text)",
    fontWeight: 700,
    margin: 0,
  },
  section: {
    borderTop: "1px solid var(--border)",
    display: "grid",
    gap: "12px",
    marginTop: "24px",
    paddingTop: "20px",
  },
  link: {
    color: "var(--accent-strong)",
    fontWeight: 700,
    textDecoration: "none",
  },
};

export function ProductionOutputDetail({
  productionOutputId,
}: ProductionOutputDetailProps) {
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [output, setOutput] = useState<ProductionOutputData | null>(null);
  const [shiftReport, setShiftReport] = useState<ShiftReportReference | null>(null);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [productionOrders, setProductionOrders] = useState<ProductionOrderOption[]>([]);
  const [orderItems, setOrderItems] = useState<ProductionOrderItemListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadProductionOutput() {
      try {
        setIsLoading(true);
        setError(null);

        const response = await getProductionOutputById(productionOutputId);
        if (response.shift_report_id) {
          getShiftReportById(response.shift_report_id)
            .then((report) => {
              if (isMounted) {
                setShiftReport(report);
              }
            })
            .catch(() => undefined);
        } else if (isMounted) {
          setShiftReport(null);
        }

        const [workCentersResponse, productionOrdersResponse, orderItemsResponse] =
          await Promise.all([
            getWorkCenters().catch(() => []),
            getProductionOrders().catch(() => []),
            getItemsByOrder(response.production_order_id).catch(() => []),
          ]);

        if (isMounted) {
          setOutput(response);
          setWorkCenters(workCentersResponse);
          setProductionOrders(productionOrdersResponse);
          setOrderItems(orderItemsResponse);
        }
      } catch (caughtError) {
        if (isMounted) {
          setError(getApiErrorMessage(caughtError, messages));
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadProductionOutput();

    return () => {
      isMounted = false;
    };
  }, [productionOutputId]);

  if (isLoading) {
    return (
      <PageFrame
        section="Production"
        title="Production Output"
        subtitle={messages("loading.default")}
      >
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          {messages("loading.default")}
        </div>
      </PageFrame>
    );
  }

  if (error || !output) {
    return (
      <PageFrame
        section="Production"
        title="Production Output"
        subtitle="The requested production output could not be loaded."
        action={
          <Link href="/production-outputs" style={sharedStyles.secondaryButton}>
            Back to Production Outputs
          </Link>
        }
      >
        <div style={sharedStyles.error} role="alert">
          {error ?? "Production output not found."}
        </div>
      </PageFrame>
    );
  }

  const orderItem = output.production_order_item_id
    ? orderItems.find((item) => item.id === output.production_order_item_id)
    : null;

  return (
    <PageFrame
      section="Production"
      title={`Production Output - ${fmt.date(output.output_date)}`}
      subtitle="Production output detail and linked production context."
      action={
        <Link href="/production-outputs" style={sharedStyles.secondaryButton}>
          Back to Production Outputs
        </Link>
      }
    >
      <section style={styles.panel}>
        <div style={styles.grid}>
          <DetailValue label="Output Date" value={fmt.date(output.output_date)} />
          <DetailValue
            label="Quantity Produced"
            value={fmt.quantity(output.quantity_produced, output.unit)}
          />
          <div>
            <span style={styles.label}>Status</span>
            <ProductionOutputStatusBadge status={output.output_status} />
          </div>
          <DetailValue
            label="Recorded At"
            value={fmt.dateTime(output.recorded_at)}
          />
        </div>

        <section style={styles.section} aria-label="References">
          <h2 style={{ margin: 0, fontSize: "18px" }}>References</h2>
          <ReferenceLine label="Work Center">
            <Link href={`/work-centers/${output.work_center_id}`} style={styles.link}>
              {formatWorkCenterLabel(workCenters, output.work_center_id)}
            </Link>
          </ReferenceLine>
          <ReferenceLine label="Production Order">
            <Link
              href={`/production-orders/${output.production_order_id}`}
              style={styles.link}
            >
              {formatProductionOrderLabel(productionOrders, output.production_order_id)}
            </Link>
          </ReferenceLine>
          {output.production_order_item_id ? (
            <ReferenceLine label="Production Order Item">
              {orderItem ? `Line ${orderItem.line_no}` : output.production_order_item_id}
            </ReferenceLine>
          ) : null}
          {output.shift_report_id ? (
            <ReferenceLine label="Shift Report">
              <Link href={`/shift-reports/${output.shift_report_id}`} style={styles.link}>
                {shiftReport ? fmt.date(shiftReport.report_date) : output.shift_report_id}
              </Link>
            </ReferenceLine>
          ) : (
            <ReferenceLine label="Shift Report">
              Recorded directly against order (no shift context)
            </ReferenceLine>
          )}
        </section>

        <section style={styles.section} aria-label="Notes">
          <h2 style={{ margin: 0, fontSize: "18px" }}>Notes</h2>
          <p style={{ margin: 0 }}>{output.notes || "No notes recorded."}</p>
        </section>
      </section>
    </PageFrame>
  );
}

function DetailValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span style={styles.label}>{label}</span>
      <p style={styles.value}>{value}</p>
    </div>
  );
}

function ReferenceLine({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <span style={styles.label}>{label}</span>
      <p style={styles.value}>{children}</p>
    </div>
  );
}
