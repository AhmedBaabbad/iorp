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
import { getDowntimeEvents } from "../api/downtime-events-api";
import type {
  DowntimeCategory,
  DowntimeEventListFilters,
  DowntimeEventListItem,
  DowntimeStatus,
} from "../types";
import { DowntimeCategoryBadge } from "./DowntimeCategoryBadge";
import { DowntimeStatusBadge } from "./DowntimeStatusBadge";
import {
  downtimeCategories,
  formatCategory,
  formatWorkCenterLabel,
  type ProductionOrderOption,
  type WorkCenterOption,
} from "./downtime-events-utils";

type FilterValues = {
  work_center_id: string;
  production_order_id: string;
  status: "" | DowntimeStatus;
  category: "" | DowntimeCategory;
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
  work_center_id: "",
  production_order_id: "",
  status: "",
  category: "",
};

export function DowntimeEventsList() {
  const tEnums = useTranslations();
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const fmt = useFormatter();
  const [events, setEvents] = useState<DowntimeEventListItem[]>([]);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [productionOrders, setProductionOrders] = useState<ProductionOrderOption[]>([]);
  const [filters, setFilters] = useState<FilterValues>(defaultFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadDowntimeEvents = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const [eventsResponse, workCentersResponse, productionOrdersResponse] =
        await Promise.all([
          getDowntimeEvents(toApiFilters(filters)),
          getWorkCenters().catch(() => []),
          getProductionOrders().catch(() => []),
        ]);

      if (isMountedRef.current) {
        setEvents(eventsResponse);
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
    void loadDowntimeEvents();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadDowntimeEvents]);

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
      title="Downtime Events"
      subtitle="Track machine and process stoppages by work center and production context."
      action={
        <Link href="/downtime-events/new" style={sharedStyles.button}>
          New Downtime Event
        </Link>
      }
    >
      <section style={styles.filters} aria-label="Downtime event filters">
        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>Status</span>
          <select
            style={sharedStyles.input}
            value={filters.status}
            onChange={(event) =>
              updateFilter("status", event.target.value as FilterValues["status"])
            }
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="closed">Closed</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>Category</span>
          <select
            style={sharedStyles.input}
            value={filters.category}
            onChange={(event) =>
              updateFilter("category", event.target.value as FilterValues["category"])
            }
          >
            <option value="">All categories</option>
            {downtimeCategories.map((category) => (
              <option key={category} value={category}>
                {formatCategory(category, tEnums)}
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
            onClick={() => void loadDowntimeEvents()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && events.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>
            No downtime events found
          </h2>
          <p style={{ margin: "0 0 18px" }}>
            Record a downtime event, or adjust the filters.
          </p>
          <Link href="/downtime-events/new" style={sharedStyles.button}>
            Record downtime event
          </Link>
        </section>
      ) : null}

      {!isLoading && !error && events.length > 0 ? (
        <section style={styles.panel} aria-label="Downtime events list">
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Start Time</th>
                  <th style={styles.th}>End Time</th>
                  <th style={styles.th}>Duration</th>
                  <th style={styles.th}>Category</th>
                  <th style={styles.th}>Status</th>
                  <th style={styles.th}>Work Center</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td style={styles.td}>
                      <Link href={`/downtime-events/${event.id}`} style={styles.link}>
                        {fmt.dateTime(event.start_time)}
                      </Link>
                    </td>
                    <td style={styles.td}>
                      {event.end_time ? fmt.dateTime(event.end_time) : "Ongoing"}
                    </td>
                    <td style={styles.td}>{fmt.duration(event.duration_minutes)}</td>
                    <td style={styles.td}>
                      <DowntimeCategoryBadge category={event.category} />
                    </td>
                    <td style={styles.td}>
                      <DowntimeStatusBadge status={event.status} />
                    </td>
                    <td style={styles.td}>
                      {formatWorkCenterLabel(workCenters, event.work_center_id)}
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

function toApiFilters(filters: FilterValues): DowntimeEventListFilters {
  return {
    work_center_id: filters.work_center_id || undefined,
    production_order_id: filters.production_order_id || undefined,
    status: filters.status || undefined,
    category: filters.category || undefined,
  };
}
