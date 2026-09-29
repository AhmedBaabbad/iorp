"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getProductionOrders } from "@/features/production-orders";
import { getWorkCenters } from "@/features/work-centers";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getWasteRecords } from "../api/waste-records-api";
import type {
  WasteCategory,
  WasteRecordListFilters,
  WasteRecordListItem,
} from "../types";
import { WasteCategoryBadge } from "./WasteCategoryBadge";
import {
  formatProductionOrderLabel,
  formatWasteCategory,
  formatWorkCenterLabel,
  truncateText,
  wasteCategories,
  type ProductionOrderOption,
  type WorkCenterOption,
} from "./waste-records-utils";

type FilterValues = {
  production_order_id: string;
  shift_report_id: string;
  work_center_id: string;
  waste_category: "" | WasteCategory;
  waste_date: string;
};

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
  },
  filters: {
    display: "grid",
    gap: "14px",
    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
    marginBottom: "18px",
  },
  tableWrap: {
    overflowX: "auto",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
  },
  th: {
    borderBottom: "1px solid var(--border)",
    color: "var(--text-muted)",
    fontSize: "13px",
    padding: "14px 16px",
    textAlign: "left",
  },
  td: {
    borderBottom: "1px solid var(--border)",
    padding: "14px 16px",
    verticalAlign: "middle",
  },
  link: {
    color: "var(--accent-strong)",
    fontWeight: 700,
    textDecoration: "none",
  },
};

const defaultFilters: FilterValues = {
  production_order_id: "",
  shift_report_id: "",
  work_center_id: "",
  waste_category: "",
  waste_date: "",
};

export function WasteRecordsList() {
  const tEnums = useTranslations();
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const fmt = useFormatter();
  const [records, setRecords] = useState<WasteRecordListItem[]>([]);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [productionOrders, setProductionOrders] = useState<ProductionOrderOption[]>([]);
  const [filters, setFilters] = useState<FilterValues>(defaultFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadWasteRecords = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const [recordsResponse, workCentersResponse, productionOrdersResponse] =
        await Promise.all([
          getWasteRecords(toApiFilters(filters)),
          getWorkCenters().catch(() => []),
          getProductionOrders().catch(() => []),
        ]);

      if (isMountedRef.current) {
        setRecords(recordsResponse);
        setWorkCenters(workCentersResponse);
        setProductionOrders(productionOrdersResponse);
      }
    } catch (caughtError) {
      if (isMountedRef.current) {
        setError(getApiErrorMessage(caughtError, messages));
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [filters]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadWasteRecords();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadWasteRecords]);

  function updateFilter<TField extends keyof FilterValues>(
    field: TField,
    value: FilterValues[TField],
  ) {
    setFilters((current) => ({
      ...current,
      [field]: value,
    }));
  }

  return (
    <PageFrame
      section="Production"
      title="Waste Records"
      subtitle="Track recorded production waste by order, work center, and category."
      action={
        <Link href="/waste-records/new" style={sharedStyles.button}>
          New Waste Record
        </Link>
      }
    >
      <section style={styles.filters} aria-label="Waste record filters">
        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>Waste Category</span>
          <select
            style={sharedStyles.input}
            value={filters.waste_category}
            onChange={(event) =>
              updateFilter(
                "waste_category",
                event.target.value as FilterValues["waste_category"],
              )
            }
          >
            <option value="">All categories</option>
            {wasteCategories.map((category) => (
              <option key={category} value={category}>
                {formatWasteCategory(category, tEnums)}
              </option>
            ))}
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>Work Center</span>
          <select
            style={sharedStyles.input}
            value={filters.work_center_id}
            onChange={(event) => updateFilter("work_center_id", event.target.value)}
          >
            <option value="">All work centers</option>
            {workCenters.map((workCenter) => (
              <option key={workCenter.id} value={workCenter.id}>
                {workCenter.code} - {workCenter.name}
              </option>
            ))}
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>Production Order</span>
          <select
            style={sharedStyles.input}
            value={filters.production_order_id}
            onChange={(event) => updateFilter("production_order_id", event.target.value)}
          >
            <option value="">All production orders</option>
            {productionOrders.map((order) => (
              <option key={order.id} value={order.id}>
                {order.production_order_number} - {order.product_type}
              </option>
            ))}
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>Shift Report ID</span>
          <input
            style={sharedStyles.input}
            value={filters.shift_report_id}
            onChange={(event) => updateFilter("shift_report_id", event.target.value)}
          />
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>Waste Date</span>
          <input
            style={sharedStyles.input}
            type="date"
            value={filters.waste_date}
            onChange={(event) => updateFilter("waste_date", event.target.value)}
          />
        </label>
      </section>

      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          {messages("loading.default")}
        </div>
      ) : null}

      {!isLoading && error ? (
        <div style={{ display: "grid", gap: "12px" }}>
          <div style={sharedStyles.error} role="alert">
            {error}
          </div>
          <button
            style={{ ...sharedStyles.secondaryButton, width: "fit-content" }}
            type="button"
            onClick={() => void loadWasteRecords()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && records.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>
            No waste records found
          </h2>
          <p style={{ margin: "0 0 18px" }}>
            Record production waste, or adjust the filters.
          </p>
          <Link href="/waste-records/new" style={sharedStyles.button}>
            Record waste
          </Link>
        </section>
      ) : null}

      {!isLoading && !error && records.length > 0 ? (
        <section style={styles.panel} aria-label="Waste records list">
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Waste Date</th>
                  <th style={styles.th}>Quantity</th>
                  <th style={styles.th}>Category</th>
                  <th style={styles.th}>Work Center</th>
                  <th style={styles.th}>Production Order</th>
                  <th style={styles.th}>Reason</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr key={record.id}>
                    <td style={styles.td}>
                      <Link href={`/waste-records/${record.id}`} style={styles.link}>
                        {fmt.date(record.waste_date)}
                      </Link>
                    </td>
                    <td style={styles.td}>
                      {fmt.quantity(record.quantity_wasted, record.unit)}
                    </td>
                    <td style={styles.td}>
                      <WasteCategoryBadge category={record.waste_category} />
                    </td>
                    <td style={styles.td}>
                      {formatWorkCenterLabel(workCenters, record.work_center_id)}
                    </td>
                    <td style={styles.td}>
                      {formatProductionOrderLabel(
                        productionOrders,
                        record.production_order_id,
                      )}
                    </td>
                    <td style={styles.td}>{truncateText(record.reason_code || "-", 46)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </PageFrame>
  );
}

function toApiFilters(filters: FilterValues): WasteRecordListFilters {
  return {
    production_order_id: filters.production_order_id || undefined,
    shift_report_id: filters.shift_report_id || undefined,
    work_center_id: filters.work_center_id || undefined,
    waste_category: filters.waste_category || undefined,
    waste_date: filters.waste_date || undefined,
  };
}
