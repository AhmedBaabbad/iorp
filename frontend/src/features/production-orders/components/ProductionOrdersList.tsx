"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getWorkCenters } from "@/features/work-centers";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getProductionOrders } from "../api/production-orders-api";
import type {
  ProductionOrderListFilters,
  ProductionOrderListItem,
  ProductionOrderPriority,
  ProductionOrderStatus,
} from "../types";
import { PRODUCTION_ORDER_STATUSES } from "../types";
import { ProductionOrderPriorityBadge } from "./ProductionOrderPriorityBadge";
import { ProductionOrderStatusBadge } from "./ProductionOrderStatusBadge";
import { usePermission } from "@/features/auth/permission-hooks";
import { P } from "@/lib/production-permissions";
import { useProductName } from "@/features/masterdata";

type WorkCenterOption = {
  id: string;
  code: string;
  name: string;
};

type FilterValues = {
  status: "" | ProductionOrderStatus;
  priority: "" | ProductionOrderPriority;
  work_center_id: string;
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
  status: "",
  priority: "",
  work_center_id: "",
};

export function ProductionOrdersList() {
  const t = useTranslations("production.productionOrders");
  const canCreateOrder = usePermission(P.ORDERS_CREATE);
  const canAllocate = usePermission(P.PLANNING_ALLOCATE);
  const canCreate = canCreateOrder && canAllocate; // orders are created by allocating demand in planning
  const common = useTranslations("common");
  const enums = useTranslations();
  const messages = useTranslations("messages");
  const productName = useProductName();  // MD-001: the product's name, not its key
  const fmt = useFormatter();
  const [orders, setOrders] = useState<ProductionOrderListItem[]>([]);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [filters, setFilters] = useState<FilterValues>(defaultFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadProductionOrders = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const [ordersResponse, workCentersResponse] = await Promise.all([
        getProductionOrders(toApiFilters(filters)),
        getWorkCenters().catch(() => []),
      ]);

      if (isMountedRef.current) {
        setOrders(ordersResponse);
        setWorkCenters(workCentersResponse);
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
  }, [filters, t]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadProductionOrders();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadProductionOrders]);

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
      title={t("listTitle")}
      subtitle={t("subtitle")}
      action={canCreate ? (
        <Link href="/production/planning" style={sharedStyles.button}>
          {t("newButton")}
        </Link>
      ) : undefined}
    >
      <section style={styles.filters} aria-label={t("filtersAria")}>
        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.status")}</span>
          <select
            style={sharedStyles.input}
            value={filters.status}
            onChange={(event) =>
              updateFilter("status", event.target.value as FilterValues["status"])
            }
          >
            <option value="">{t("allStatuses")}</option>
            {PRODUCTION_ORDER_STATUSES.map((value) => (
              <option key={value} value={value}>{enums(`enums.productionOrder.status.${value}`)}</option>
            ))}
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.priority")}</span>
          <select
            style={sharedStyles.input}
            value={filters.priority}
            onChange={(event) =>
              updateFilter("priority", event.target.value as FilterValues["priority"])
            }
          >
            <option value="">{t("allPriorities")}</option>
            <option value="urgent">{enums("enums.productionOrder.priority.urgent")}</option>
            <option value="high">{enums("enums.productionOrder.priority.high")}</option>
            <option value="normal">{enums("enums.productionOrder.priority.normal")}</option>
            <option value="low">{enums("enums.productionOrder.priority.low")}</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.workCenter")}</span>
          <select
            style={sharedStyles.input}
            value={filters.work_center_id}
            onChange={(event) => updateFilter("work_center_id", event.target.value)}
          >
            <option value="">{t("allWorkCenters")}</option>
            {workCenters.map((workCenter) => (
              <option key={workCenter.id} value={workCenter.id}>
                {workCenter.code} - {workCenter.name}
              </option>
            ))}
          </select>
        </label>
      </section>

      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          {t("loading")}
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
            onClick={() => void loadProductionOrders()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && orders.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>
            {t("empty")}
          </h2>
          <p style={{ margin: "0 0 18px" }}>
            {t("createFirst")}
          </p>
          {canCreate ? (
            <Link href="/production/planning" style={sharedStyles.button}>
              {t("createButton")}
            </Link>
          ) : null}
        </section>
      ) : null}

      {!isLoading && !error && orders.length > 0 ? (
        <section style={styles.panel} aria-label={t("listAria")}>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t("fields.orderNumber")}</th>
                  <th style={styles.th}>{t("fields.product")}</th>
                  <th style={styles.th}>{t("fields.quantity")}</th>
                  <th style={styles.th}>{t("fields.status")}</th>
                  <th style={styles.th}>{t("fields.priority")}</th>
                  <th style={styles.th}>{t("fields.startDate")}</th>
                  <th style={styles.th}>{t("fields.workCenter")}</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.id}>
                    <td style={styles.td}>
                      <Link href={`/production-orders/${order.id}`} style={styles.link}>
                        {order.production_order_number}
                      </Link>
                    </td>
                    <td style={styles.td}>{productName(order.product_type)}</td>
                    <td style={styles.td}>
                      {fmt.quantity(order.planned_quantity, order.unit)}
                    </td>
                    <td style={styles.td}>
                      <ProductionOrderStatusBadge status={order.status} />
                    </td>
                    <td style={styles.td}>
                      <ProductionOrderPriorityBadge priority={order.priority} />
                    </td>
                    <td style={styles.td}>{fmt.date(order.planned_start_date)}</td>
                    <td style={styles.td}>
                      {formatWorkCenterLabel(workCenters, order.work_center_id)}
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

function toApiFilters(filters: FilterValues): ProductionOrderListFilters {
  return {
    status: filters.status || undefined,
    priority: filters.priority || undefined,
    work_center_id: filters.work_center_id || undefined,
  };
}

function formatWorkCenterLabel(workCenters: WorkCenterOption[], workCenterId: string) {
  const workCenter = workCenters.find((item) => item.id === workCenterId);
  return workCenter ? `${workCenter.code} - ${workCenter.name}` : workCenterId;
}
