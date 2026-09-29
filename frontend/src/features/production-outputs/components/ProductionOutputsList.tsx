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
import { getProductionOutputs } from "../api/production-outputs-api";
import type {
  ProductionOutputListFilters,
  ProductionOutputListItem,
  ProductionOutputStatus,
} from "../types";
import { ProductionOutputStatusBadge } from "./ProductionOutputStatusBadge";
import {
  formatProductionOrderLabel,
  formatWorkCenterLabel,
  type ProductionOrderOption,
  type WorkCenterOption,
} from "./production-output-utils";

type FilterValues = {
  production_order_id: string;
  shift_report_id: string;
  work_center_id: string;
  output_date: string;
  output_status: "" | ProductionOutputStatus;
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
  output_date: "",
  output_status: "",
};

export function ProductionOutputsList() {
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const fmt = useFormatter();
  const [outputs, setOutputs] = useState<ProductionOutputListItem[]>([]);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [productionOrders, setProductionOrders] = useState<ProductionOrderOption[]>([]);
  const [filters, setFilters] = useState<FilterValues>(defaultFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadProductionOutputs = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const [outputsResponse, workCentersResponse, productionOrdersResponse] =
        await Promise.all([
          getProductionOutputs(toApiFilters(filters)),
          getWorkCenters().catch(() => []),
          getProductionOrders().catch(() => []),
        ]);

      if (isMountedRef.current) {
        setOutputs(outputsResponse);
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
    void loadProductionOutputs();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadProductionOutputs]);

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
      title="Production Outputs"
      subtitle="Track recorded output quantities by order, work center, and shift context."
      action={
        <Link href="/production-outputs/new" style={sharedStyles.button}>
          New Output
        </Link>
      }
    >
      <section style={styles.filters} aria-label="Production output filters">
        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>Status</span>
          <select
            style={sharedStyles.input}
            value={filters.output_status}
            onChange={(event) =>
              updateFilter(
                "output_status",
                event.target.value as FilterValues["output_status"],
              )
            }
          >
            <option value="">All statuses</option>
            <option value="recorded">Recorded</option>
            <option value="verified">Verified</option>
            <option value="posted">Posted</option>
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
          <span style={sharedStyles.label}>Output Date</span>
          <input
            style={sharedStyles.input}
            type="date"
            value={filters.output_date}
            onChange={(event) => updateFilter("output_date", event.target.value)}
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
            onClick={() => void loadProductionOutputs()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && outputs.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>
            No production outputs found
          </h2>
          <p style={{ margin: "0 0 18px" }}>
            Record production output, or adjust the filters.
          </p>
          <Link href="/production-outputs/new" style={sharedStyles.button}>
            Record production output
          </Link>
        </section>
      ) : null}

      {!isLoading && !error && outputs.length > 0 ? (
        <section style={styles.panel} aria-label="Production outputs list">
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Output Date</th>
                  <th style={styles.th}>Quantity</th>
                  <th style={styles.th}>Status</th>
                  <th style={styles.th}>Production Order</th>
                  <th style={styles.th}>Work Center</th>
                </tr>
              </thead>
              <tbody>
                {outputs.map((output) => (
                  <tr key={output.id}>
                    <td style={styles.td}>
                      <Link href={`/production-outputs/${output.id}`} style={styles.link}>
                        {fmt.date(output.output_date)}
                      </Link>
                    </td>
                    <td style={styles.td}>
                      {fmt.quantity(output.quantity_produced, output.unit)}
                    </td>
                    <td style={styles.td}>
                      <ProductionOutputStatusBadge status={output.output_status} />
                    </td>
                    <td style={styles.td}>
                      {formatProductionOrderLabel(productionOrders, output.production_order_id)}
                    </td>
                    <td style={styles.td}>
                      {formatWorkCenterLabel(workCenters, output.work_center_id)}
                    </td>
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

function toApiFilters(filters: FilterValues): ProductionOutputListFilters {
  return {
    production_order_id: filters.production_order_id || undefined,
    shift_report_id: filters.shift_report_id || undefined,
    work_center_id: filters.work_center_id || undefined,
    output_date: filters.output_date || undefined,
    output_status: filters.output_status || undefined,
  };
}
