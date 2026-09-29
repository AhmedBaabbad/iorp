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
import { getWasteRecordById } from "../api/waste-records-api";
import type { WasteRecordData } from "../types";
import { WasteCategoryBadge } from "./WasteCategoryBadge";
import {
  formatProductionOrderLabel,
  formatWorkCenterLabel,
  type ProductionOrderOption,
  type WorkCenterOption,
} from "./waste-records-utils";

type WasteRecordDetailProps = {
  wasteRecordId: string;
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

export function WasteRecordDetail({ wasteRecordId }: WasteRecordDetailProps) {
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [record, setRecord] = useState<WasteRecordData | null>(null);
  const [shiftReport, setShiftReport] = useState<ShiftReportReference | null>(null);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [productionOrders, setProductionOrders] = useState<ProductionOrderOption[]>([]);
  const [orderItems, setOrderItems] = useState<ProductionOrderItemListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadWasteRecord() {
      try {
        setIsLoading(true);
        setError(null);

        const response = await getWasteRecordById(wasteRecordId);
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
          setRecord(response);
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

    void loadWasteRecord();

    return () => {
      isMounted = false;
    };
  }, [wasteRecordId]);

  if (isLoading) {
    return (
      <PageFrame section="Production" title="Waste Record" subtitle={messages("loading.default")}>
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          {messages("loading.default")}
        </div>
      </PageFrame>
    );
  }

  if (error || !record) {
    return (
      <PageFrame
        section="Production"
        title="Waste Record"
        subtitle="The requested waste record could not be loaded."
        action={
          <Link href="/waste-records" style={sharedStyles.secondaryButton}>
            Back to Waste Records
          </Link>
        }
      >
        <div style={sharedStyles.error} role="alert">
          {error ?? "Waste record not found."}
        </div>
      </PageFrame>
    );
  }

  const orderItem = record.production_order_item_id
    ? orderItems.find((item) => item.id === record.production_order_item_id)
    : null;

  return (
    <PageFrame
      section="Production"
      title={`Waste Record - ${fmt.date(record.waste_date)}`}
      subtitle="Waste record detail and linked production context."
      action={
        <Link href="/waste-records" style={sharedStyles.secondaryButton}>
          Back to Waste Records
        </Link>
      }
    >
      <section style={styles.panel}>
        <div style={styles.grid}>
          <DetailValue label="Waste Date" value={fmt.date(record.waste_date)} />
          <DetailValue
            label="Quantity Wasted"
            value={fmt.quantity(record.quantity_wasted, record.unit)}
          />
          <div>
            <span style={styles.label}>Waste Category</span>
            <WasteCategoryBadge category={record.waste_category} />
          </div>
          <DetailValue label="Reason Code" value={record.reason_code ?? "Not specified"} />
        </div>

        <section style={styles.section} aria-label="References">
          <h2 style={{ margin: 0, fontSize: "18px" }}>References</h2>
          <ReferenceLine label="Work Center">
            <Link href={`/work-centers/${record.work_center_id}`} style={styles.link}>
              {formatWorkCenterLabel(workCenters, record.work_center_id)}
            </Link>
          </ReferenceLine>
          <ReferenceLine label="Production Order">
            <Link
              href={`/production-orders/${record.production_order_id}`}
              style={styles.link}
            >
              {formatProductionOrderLabel(productionOrders, record.production_order_id)}
            </Link>
          </ReferenceLine>
          {record.production_order_item_id ? (
            <ReferenceLine label="Production Order Item">
              {orderItem ? `Line ${orderItem.line_no}` : record.production_order_item_id}
            </ReferenceLine>
          ) : null}
          {record.shift_report_id ? (
            <ReferenceLine label="Shift Report">
              <Link href={`/shift-reports/${record.shift_report_id}`} style={styles.link}>
                {shiftReport ? fmt.date(shiftReport.report_date) : record.shift_report_id}
              </Link>
            </ReferenceLine>
          ) : null}
        </section>

        <section style={styles.section} aria-label="Notes">
          <h2 style={{ margin: 0, fontSize: "18px" }}>Notes</h2>
          <p style={{ margin: 0 }}>{record.notes || "No notes recorded."}</p>
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
