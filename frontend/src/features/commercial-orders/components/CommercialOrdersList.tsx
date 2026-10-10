"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { PermissionGuard } from "@/components/PermissionGuard";
import { ListToolbar } from "@/components/pagination/ListToolbar";
import { Pagination } from "@/components/pagination/Pagination";
import { useListQuery, type Page } from "@/lib/pagination";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { deleteCommercialOrder, getOrderDeletionImpact, listCommercialOrders } from "../api/commercial-orders-api";
import type { CommercialOrderListItem, OrderDeletionImpact } from "../types";
import { CommercialOrderStatusBadge } from "./CommercialOrderStatusBadge";

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
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
  actions: {
    display: "flex",
    flexWrap: "nowrap",
    gap: "8px",
    whiteSpace: "nowrap",
  },
  actionButton: {
    ...sharedStyles.secondaryButton,
    fontSize: "13px",
    minHeight: "34px",
    padding: "6px 12px",
  },
  deleteButton: {
    ...sharedStyles.secondaryButton,
    borderColor: "color-mix(in srgb, var(--danger) 35%, var(--surface))",
    color: "var(--danger)",
    fontSize: "13px",
    minHeight: "34px",
    padding: "6px 12px",
  },
  success: {
    background: "var(--success-soft)",
    border: "1px solid color-mix(in srgb, var(--success) 35%, var(--surface))",
    borderRadius: "6px",
    color: "var(--success)",
    fontSize: "14px",
    padding: "12px 14px",
  },
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "var(--overlay)",
    backdropFilter: "blur(2px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modal: {
    background: "var(--surface)",
    borderRadius: "14px",
    boxShadow: "0 24px 64px rgba(15, 23, 42, 0.28), 0 4px 16px rgba(15, 23, 42, 0.12)",
    padding: "32px",
    maxWidth: "460px",
    width: "90%",
    display: "grid",
    gap: "20px",
  },
  modalIcon: {
    width: "48px",
    height: "48px",
    borderRadius: "50%",
    background: "var(--surface-muted)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "22px",
    margin: "0 auto",
  },
  modalTitle: {
    fontSize: "18px",
    fontWeight: 700,
    color: "var(--text)",
    margin: 0,
    textAlign: "center" as const,
  },
  modalBody: {
    fontSize: "14px",
    color: "var(--text-muted)",
    margin: 0,
    lineHeight: "1.7",
    textAlign: "center" as const,
  },
  modalActions: {
    display: "flex",
    gap: "12px",
    justifyContent: "center",
    flexWrap: "wrap" as const,
  },
  modalCancelButton: {
    ...sharedStyles.secondaryButton,
    minHeight: "40px",
    padding: "10px 24px",
    fontSize: "14px",
  },
  modalDeleteButton: {
    background: "var(--danger)",
    border: "none",
    borderRadius: "8px",
    color: "var(--on-accent)",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: 600,
    minHeight: "40px",
    padding: "10px 24px",
  },
};

export function CommercialOrdersList() {
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const t = useTranslations("commercial.commercialOrders");
  const fmt = useFormatter();
  const tStatus = useTranslations("enums.commercialOrder.status");
  // ARCH-PAGE-001: one page from the server (50 rows by default); page, search and status live in the address.
  const list = useListQuery(["search", "status"] as const);
  const apiQuery = list.apiQuery();
  const [data, setData] = useState<Page<CommercialOrderListItem> | null>(null);
  const orders = data?.items ?? [];
  const filtered = Boolean(list.filters.search || list.filters.status);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [loadingImpactId, setLoadingImpactId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<{ id: string; impact: OrderDeletionImpact } | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadOrders = useCallback(async () => {
    if (!isMountedRef.current) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await listCommercialOrders(apiQuery);
      if (isMountedRef.current) {
        setData(response);
        if (response.items.length === 0 && response.total > 0 && list.page > response.pages) list.setPage(response.pages);
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
  }, [messages, apiQuery]); // eslint-disable-line react-hooks/exhaustive-deps -- list changes every render; apiQuery is what matters

  useEffect(() => {
    isMountedRef.current = true;
    void loadOrders();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadOrders]);

  async function handleDelete(orderId: string) {
    setLoadingImpactId(orderId);
    setDeleteError(null);
    try {
      const impact = await getOrderDeletionImpact(orderId);
      if (isMountedRef.current) {
        setPendingDelete({ id: orderId, impact });
      }
    } catch {
      // silently ignore — impact fetch failure doesn't block the user
    } finally {
      if (isMountedRef.current) {
        setLoadingImpactId(null);
      }
    }
  }

  function handleCancelDelete() {
    setPendingDelete(null);
    setDeleteError(null);
  }

  async function handleConfirmDelete() {
    if (!pendingDelete) return;
    const idToDelete = pendingDelete.id;
    const capturedImpact = pendingDelete.impact;
    setPendingDelete(null);
    setDeletingId(idToDelete);
    setSuccessMessage(null);

    try {
      await deleteCommercialOrder(idToDelete);
      if (isMountedRef.current) {
        setSuccessMessage(t("deleteSuccess"));
        await loadOrders();
      }
    } catch (caughtError) {
      if (isMountedRef.current) {
        setDeleteError(getApiErrorMessage(caughtError, messages));
        setPendingDelete({ id: idToDelete, impact: capturedImpact });
      }
    } finally {
      if (isMountedRef.current) {
        setDeletingId(null);
      }
    }
  }

  return (
    <>
      {pendingDelete ? (
        <div style={styles.backdrop} onClick={handleCancelDelete}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalIcon}>🗑️</div>
            <h2 style={styles.modalTitle}>{t("delete.confirmTitle")}</h2>
            <p style={styles.modalBody}>{t("delete.confirmMessage")}</p>
            {pendingDelete.impact.items > 0 && (
              <ul style={{ margin: 0, padding: "0 0 0 20px", color: "var(--text-muted)", fontSize: "14px", lineHeight: "1.8" }}>
                <li>{t("delete.itemsCount", { count: pendingDelete.impact.items })}</li>
              </ul>
            )}

            {deleteError ? (
              <p style={{ margin: 0, color: "var(--danger)", fontSize: "13px", textAlign: "center" }}>
                {deleteError}
              </p>
            ) : null}

            <div style={styles.modalActions}>
              <button type="button" style={styles.modalCancelButton} onClick={handleCancelDelete}>
                {t("delete.cancel")}
              </button>
              <button
                type="button"
                style={styles.modalDeleteButton}
                disabled={!!deletingId}
                onClick={() => void handleConfirmDelete()}
              >
                {deletingId ? t("delete.deleting") : t("delete.confirm")}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <PageFrame
        title={t("listTitle")}
        subtitle={t("subtitle")}
        action={
          <PermissionGuard code="commercial:orders:create"><Link href="/commercial-orders/new" style={sharedStyles.button}>
            {t("newButton")}
          </Link></PermissionGuard>
        }
      >
        <ListToolbar search={list.filters.search} onSearch={(v) => list.setFilter("search", v)} searchHint={t("searchHint")}
          status={list.filters.status} onStatus={(v) => list.setFilter("status", v)} statusLabel={t("fields.status")}
          statuses={["draft", "confirmed", "cancelled"].map((value) => ({ value, label: tStatus(value) }))} onClear={list.clearFilters} />

        {isLoading && !data ? (
          <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{messages("loading.default")}</div>
        ) : null}

        {!isLoading && successMessage ? (
          <div style={styles.success} role="status">
            {successMessage}
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
              onClick={() => void loadOrders()}
            >
              {common("actions.retry")}
            </button>
          </div>
        ) : null}

        {!isLoading && !error && orders.length === 0 && filtered ? (
          <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>{common("listFilters.noMatches")}</section>
        ) : null}

        {!isLoading && !error && orders.length === 0 && !filtered ? (
          <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
            <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("empty")}</h2>
            <p style={{ margin: "0 0 18px" }}>{messages("empty.addFirst")}</p>
            <PermissionGuard code="commercial:orders:create"><Link href="/commercial-orders/new" style={sharedStyles.button}>
              {t("newButton")}
            </Link></PermissionGuard>
          </section>
        ) : null}

        {!error && orders.length > 0 ? (
          <section style={styles.panel} aria-label={t("listAria")}>
            <div style={styles.tableWrap}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>{t("fields.orderNumber")}</th>
                    <th style={styles.th}>{t("fields.customer")}</th>
                    <th style={styles.th}>{t("fields.quote")}</th>
                    <th style={styles.th}>{t("fields.status")}</th>
                    <th style={styles.th}>{t("fields.orderDate")}</th>
                    <th style={styles.th}>{t("fields.requestedDelivery")}</th>
                    <th style={styles.th}>{t("fields.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <tr key={order.id}>
                      <td style={styles.td}>
                        <Link href={`/commercial-orders/${order.id}`} style={styles.link}>
                          {order.order_number}
                        </Link>
                      </td>
                      <td style={styles.td}>
                        {displayValue(order.customer_name ?? order.customer_id)}
                      </td>
                      <td style={styles.td}>
                        {displayValue(
                          order.quote_id
                            ? order.quote_number ?? order.quote_id
                            : null,
                        )}
                      </td>
                      <td style={styles.td}>
                        <CommercialOrderStatusBadge status={order.status} />
                      </td>
                      <td style={styles.td}>{fmt.date(order.order_date)}</td>
                      <td style={styles.td}>
                        {order.requested_delivery_date
                          ? fmt.date(order.requested_delivery_date)
                          : displayValue(null)}
                      </td>
                      <td style={styles.td}>
                        <div style={styles.actions}>
                          {order.status === "draft" ? (
                            <PermissionGuard code="commercial:orders:update"><Link
                              href={`/commercial-orders/${order.id}/edit`}
                              style={styles.actionButton}
                            >
                              {common("actions.edit")}
                            </Link></PermissionGuard>
                          ) : null}
                          <PermissionGuard code="commercial:orders:delete"><button
                            type="button"
                            style={styles.deleteButton}
                            disabled={deletingId === order.id || loadingImpactId === order.id}
                            onClick={() => void handleDelete(order.id)}
                          >
                            {deletingId === order.id || loadingImpactId === order.id
                              ? "..."
                              : common("actions.delete")}
                          </button></PermissionGuard>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data ? <Pagination page={data.page} pageSize={data.page_size} total={data.total} pages={data.pages}
              disabled={isLoading} onPage={list.setPage} onPageSize={list.setPageSize} /> : null}
          </section>
        ) : null}
      </PageFrame>
    </>
  );
}
