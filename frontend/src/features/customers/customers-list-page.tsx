"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type { CustomerDeletionImpact, CustomerListItem } from "@/types/customers";
import { deleteCustomer, getCustomerDeletionImpact, listCustomers } from "./customer-api";
import {
  CustomerPriorityBadge,
  CustomerRelationshipStageBadge,
  CustomerStatusBadge,
} from "./customer-badges";
import { PageFrame } from "@/components/layout/page-frame";
import { PermissionGuard } from "@/components/PermissionGuard";

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "#ffffff",
    border: "1px solid #d9dee7",
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
    borderBottom: "1px solid #e4e7ec",
    color: "#52606d",
    fontSize: "13px",
    padding: "14px 16px",
    textAlign: "start",
    whiteSpace: "nowrap",
  },
  td: {
    borderBottom: "1px solid #eef1f5",
    padding: "14px 16px",
    verticalAlign: "middle",
  },
  link: {
    color: "#1d4ed8",
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
    minHeight: "34px",
    padding: "6px 12px",
    fontSize: "13px",
  },
  deleteButton: {
    ...sharedStyles.secondaryButton,
    borderColor: "#fecdd3",
    color: "#be123c",
    minHeight: "34px",
    padding: "6px 12px",
    fontSize: "13px",
  },
  success: {
    background: "#dcfce7",
    border: "1px solid #bbf7d0",
    borderRadius: "6px",
    color: "#166534",
    fontSize: "14px",
    padding: "12px 14px",
  },
  // Modal styles
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(15, 23, 42, 0.55)",
    backdropFilter: "blur(2px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modal: {
    background: "#ffffff",
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
    background: "#fff1f2",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "22px",
    margin: "0 auto",
  },
  modalTitle: {
    fontSize: "18px",
    fontWeight: 700,
    color: "#0f172a",
    margin: 0,
    textAlign: "center" as const,
  },
  modalBody: {
    fontSize: "14px",
    color: "#475569",
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
  modalDeleteButton: {
    background: "#be123c",
    border: "none",
    borderRadius: "8px",
    color: "#ffffff",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: 600,
    minHeight: "40px",
    padding: "10px 24px",
  },
  modalCancelButton: {
    ...sharedStyles.secondaryButton,
    minHeight: "40px",
    padding: "10px 24px",
    fontSize: "14px",
  },
};

export function CustomersListPage() {
  const t = useTranslations("commercial.customers");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingImpactId, setLoadingImpactId] = useState<string | null>(null);
  const [deletingCustomerId, setDeletingCustomerId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<{ id: string; impact: CustomerDeletionImpact } | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadCustomers = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await listCustomers();
      if (isMountedRef.current) {
        setCustomers(response);
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
  }, [messages]);

  async function handleDelete(customerId: string) {
    setLoadingImpactId(customerId);
    setDeleteError(null);
    try {
      const impact = await getCustomerDeletionImpact(customerId);
      if (isMountedRef.current) {
        setPendingDelete({ id: customerId, impact });
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
    if (!pendingDelete) {
      return;
    }

    const idToDelete = pendingDelete.id;
    const capturedImpact = pendingDelete.impact;
    setPendingDelete(null);
    setDeletingCustomerId(idToDelete);
    setSuccessMessage(null);

    try {
      await deleteCustomer(idToDelete);
      if (isMountedRef.current) {
        setSuccessMessage(t("deleteSuccess"));
        await loadCustomers();
      }
    } catch (caughtError) {
      if (isMountedRef.current) {
        setDeleteError(getApiErrorMessage(caughtError, messages));
        setPendingDelete({ id: idToDelete, impact: capturedImpact });
      }
    } finally {
      if (isMountedRef.current) {
        setDeletingCustomerId(null);
      }
    }
  }

  useEffect(() => {
    isMountedRef.current = true;
    void loadCustomers();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadCustomers]);

  return (
    <PageFrame
      title={t("listTitle")}
      subtitle={t("subtitle")}
      action={
        <PermissionGuard code="commercial:customers:create">
          <Link href="/customers/new" style={sharedStyles.button}>
            {t("newButton")}
          </Link>
        </PermissionGuard>
      }
    >
      {pendingDelete ? (
        <div style={styles.backdrop} onClick={pendingDelete.impact.is_blocked ? handleCancelDelete : undefined}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalIcon}>{pendingDelete.impact.is_blocked ? "🚫" : "🗑️"}</div>
            <h2 style={styles.modalTitle}>
              {pendingDelete.impact.is_blocked ? t("delete.blockedTitle") : t("delete.confirmTitle")}
            </h2>

            {pendingDelete.impact.is_blocked ? (
              <>
                <p style={styles.modalBody}>{t("delete.blockedMessage")}</p>
                <ul style={{ margin: 0, padding: "0 0 0 20px", color: "#475569", fontSize: "14px", lineHeight: "1.8" }}>
                  {pendingDelete.impact.quotes > 0 && (
                    <li>{t("delete.quotesCount", { count: pendingDelete.impact.quotes })}</li>
                  )}
                  {pendingDelete.impact.orders > 0 && (
                    <li>{t("delete.ordersCount", { count: pendingDelete.impact.orders })}</li>
                  )}
                  {pendingDelete.impact.production_demands > 0 && (
                    <li>{t("delete.demandsCount", { count: pendingDelete.impact.production_demands })}</li>
                  )}
                </ul>
              </>
            ) : (
              <>
                <p style={styles.modalBody}>{t("delete.confirmMessage")}</p>
                {(pendingDelete.impact.interactions > 0 || pendingDelete.impact.follow_ups > 0 || pendingDelete.impact.samples > 0) && (
                  <ul style={{ margin: 0, padding: "0 0 0 20px", color: "#475569", fontSize: "14px", lineHeight: "1.8" }}>
                    {pendingDelete.impact.interactions > 0 && (
                      <li>{t("delete.interactionsCount", { count: pendingDelete.impact.interactions })}</li>
                    )}
                    {pendingDelete.impact.follow_ups > 0 && (
                      <li>{t("delete.followUpsCount", { count: pendingDelete.impact.follow_ups })}</li>
                    )}
                    {pendingDelete.impact.samples > 0 && (
                      <li>{t("delete.samplesCount", { count: pendingDelete.impact.samples })}</li>
                    )}
                  </ul>
                )}
              </>
            )}

            {deleteError ? (
              <p style={{ margin: 0, color: "#be123c", fontSize: "13px", textAlign: "center" }}>
                {deleteError}
              </p>
            ) : null}

            <div style={styles.modalActions}>
              <button type="button" style={styles.modalCancelButton} onClick={handleCancelDelete}>
                {t("delete.cancel")}
              </button>
              {!pendingDelete.impact.is_blocked ? (
                <button
                  type="button"
                  style={styles.modalDeleteButton}
                  disabled={!!deletingCustomerId}
                  onClick={() => void handleConfirmDelete()}
                >
                  {deletingCustomerId ? t("delete.deleting") : t("delete.confirm")}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "#ffffff" }}>{t("loading")}</div>
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
            onClick={() => void loadCustomers()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && customers.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "#ffffff" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("empty")}</h2>
          <p style={{ margin: "0 0 18px" }}>{t("createFirst")}</p>
          <PermissionGuard code="commercial:customers:create">
            <Link href="/customers/new" style={sharedStyles.button}>
              {t("createButton")}
            </Link>
          </PermissionGuard>
        </section>
      ) : null}

      {!isLoading && !error && customers.length > 0 ? (
        <section style={styles.panel} aria-label={t("listAria")}>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t("fields.customerCode")}</th>
                  <th style={styles.th}>{t("fields.name")}</th>
                  <th style={styles.th}>{t("fields.sector")}</th>
                  <th style={styles.th}>{t("fields.phone")}</th>
                  <th style={styles.th}>{t("fields.email")}</th>
                  <th style={styles.th}>{t("fields.relationshipStage")}</th>
                  <th style={styles.th}>{t("fields.priority")}</th>
                  <th style={styles.th}>{t("fields.status")}</th>
                  <th style={styles.th}>{t("fields.salesOwner")}</th>
                  <th style={styles.th}>{t("fields.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {customers.map((customer) => (
                  <tr key={customer.id}>
                    <td style={styles.td}>{customer.customer_code}</td>
                    <td style={styles.td}>
                      <Link href={`/customers/${customer.id}`} style={styles.link}>
                        {customer.name}
                      </Link>
                    </td>
                    <td style={styles.td}>{displayValue(customer.sector)}</td>
                    <td style={styles.td}>{displayValue(customer.phone)}</td>
                    <td style={styles.td}>{displayValue(customer.email)}</td>
                    <td style={styles.td}>
                      <CustomerRelationshipStageBadge stage={customer.relationship_stage} />
                    </td>
                    <td style={styles.td}>
                      <CustomerPriorityBadge priority={customer.priority_level} />
                    </td>
                    <td style={styles.td}>
                      <CustomerStatusBadge status={customer.status} />
                    </td>
                    <td style={styles.td}>{customer.sales_owner?.full_name ?? t("noOwner")}</td>
                    <td style={styles.td}>
                      <div style={styles.actions}>
                        <PermissionGuard code="commercial:customers:update">
                          <Link href={`/customers/${customer.id}/edit`} style={styles.actionButton}>
                            {common("actions.edit")}
                          </Link>
                        </PermissionGuard>
                        <PermissionGuard code="commercial:customers:delete">
                          <button
                            type="button"
                            style={styles.deleteButton}
                            disabled={deletingCustomerId === customer.id || loadingImpactId === customer.id}
                            onClick={() => void handleDelete(customer.id)}
                          >
                            {deletingCustomerId === customer.id || loadingImpactId === customer.id
                              ? "..."
                              : common("actions.delete")}
                          </button>
                        </PermissionGuard>
                      </div>
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
