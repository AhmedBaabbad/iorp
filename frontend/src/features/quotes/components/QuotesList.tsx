"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { PermissionGuard } from "@/components/PermissionGuard";
import { ListToolbar } from "@/components/pagination/ListToolbar";
import { Pagination } from "@/components/pagination/Pagination";
import { useListQuery, type Page } from "@/lib/pagination";
import { useFormatter } from "@/hooks/useFormatter";
import type { Locale } from "@/i18n/config";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { deleteQuote, getQuoteDeletionImpact, listQuotes } from "../api/quotes-api";
import type { QuoteDeletionImpact, QuoteListItem } from "../types";
import { QuoteStatusBadge } from "./QuoteStatusBadge";
import { formatCommercialCurrency } from "./quote-utils";
import { usePermission } from "@/features/auth/permission-hooks";

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
    textAlign: "start",
    whiteSpace: "nowrap",
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
    minHeight: "34px",
    padding: "6px 12px",
    fontSize: "13px",
  },
  deleteButton: {
    ...sharedStyles.secondaryButton,
    borderColor: "color-mix(in srgb, var(--danger) 35%, var(--surface))",
    color: "var(--danger)",
    minHeight: "34px",
    padding: "6px 12px",
    fontSize: "13px",
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
  modalCancelButton: {
    ...sharedStyles.secondaryButton,
    minHeight: "40px",
    padding: "10px 24px",
    fontSize: "14px",
  },
};

export function QuotesList() {
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const t = useTranslations("commercial.quotes");
  const canSettings = usePermission("commercial:quote_settings:read");
  const locale = useLocale() as Locale;
  const fmt = useFormatter();
  const tStatus = useTranslations("enums.quote.status");
  // ARCH-PAGE-001: one page from the server (50 rows by default); page, search and status live in the address.
  const list = useListQuery(["search", "status"] as const);
  const apiQuery = list.apiQuery();
  const [data, setData] = useState<Page<QuoteListItem> | null>(null);
  const quotes = data?.items ?? [];
  const filtered = Boolean(list.filters.search || list.filters.status);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [loadingImpactId, setLoadingImpactId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<{ id: string; impact: QuoteDeletionImpact } | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadQuotes = useCallback(async () => {
    if (!isMountedRef.current) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await listQuotes(apiQuery);
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

  async function handleDelete(quoteId: string) {
    setLoadingImpactId(quoteId);
    setDeleteError(null);
    try {
      const impact = await getQuoteDeletionImpact(quoteId);
      if (isMountedRef.current) {
        setPendingDelete({ id: quoteId, impact });
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
      await deleteQuote(idToDelete);
      if (isMountedRef.current) {
        setSuccessMessage(t("deleteSuccess"));
        await loadQuotes();
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

  useEffect(() => {
    isMountedRef.current = true;
    void loadQuotes();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadQuotes]);

  return (
    <PageFrame
      title={t("listTitle")}
      subtitle={t("subtitle")}
      action={
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {canSettings ? <Link href="/quotes/settings" style={sharedStyles.secondaryButton}>{t("settings.link")}</Link> : null}
          <PermissionGuard code="commercial:quotes:create"><Link href="/quotes/new" style={sharedStyles.button}>
            {t("newButton")}
          </Link></PermissionGuard>
        </div>
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
                <ul style={{ margin: 0, padding: "0 0 0 20px", color: "var(--text-muted)", fontSize: "14px", lineHeight: "1.8" }}>
                  {pendingDelete.impact.orders > 0 && (
                    <li>{t("delete.ordersCount", { count: pendingDelete.impact.orders })}</li>
                  )}
                </ul>
              </>
            ) : (
              <>
                <p style={styles.modalBody}>{t("delete.confirmMessage")}</p>
                {pendingDelete.impact.items > 0 && (
                  <ul style={{ margin: 0, padding: "0 0 0 20px", color: "var(--text-muted)", fontSize: "14px", lineHeight: "1.8" }}>
                    <li>{t("delete.itemsCount", { count: pendingDelete.impact.items })}</li>
                  </ul>
                )}
              </>
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
              {!pendingDelete.impact.is_blocked ? (
                <button
                  type="button"
                  style={styles.modalDeleteButton}
                  disabled={!!deletingId}
                  onClick={() => void handleConfirmDelete()}
                >
                  {deletingId ? t("delete.deleting") : t("delete.confirm")}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      <ListToolbar search={list.filters.search} onSearch={(v) => list.setFilter("search", v)} searchHint={t("searchHint")}

        status={list.filters.status} onStatus={(v) => list.setFilter("status", v)} statusLabel={t("fields.status")}

        statuses={["draft", "issued", "accepted", "rejected", "expired"].map((value) => ({ value, label: tStatus(value) }))} onClear={list.clearFilters} />


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
            onClick={() => void loadQuotes()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && quotes.length === 0 && filtered ? (

        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>{common("listFilters.noMatches")}</section>

      ) : null}


      {!isLoading && !error && quotes.length === 0 && !filtered ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("empty")}</h2>
          <p style={{ margin: "0 0 18px" }}>{messages("empty.addFirst")}</p>
          <PermissionGuard code="commercial:quotes:create"><Link href="/quotes/new" style={sharedStyles.button}>
            {t("newButton")}
          </Link></PermissionGuard>
        </section>
      ) : null}

      {!error && quotes.length > 0 ? (
        <section style={styles.panel} aria-label={t("listAria")}>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t("fields.quoteNumber")}</th>
                  <th style={styles.th}>{t("fields.customer")}</th>
                  <th style={styles.th}>{t("fields.status")}</th>
                  <th style={styles.th}>{t("fields.quoteDate")}</th>
                  <th style={styles.th}>{t("fields.validUntil")}</th>
                  <th style={styles.th}>{t("fields.total")}</th>
                  <th style={styles.th}>{t("fields.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {quotes.map((quote) => (
                  <tr key={quote.id}>
                    <td style={styles.td}>
                      <Link href={`/quotes/${quote.id}`} style={styles.link}>
                        {quote.quote_number}
                      </Link>
                    </td>
                    <td style={styles.td}>
                      {displayValue(quote.customer_name ?? quote.customer_id)}
                    </td>
                    <td style={styles.td}>
                      <QuoteStatusBadge status={quote.status} />
                    </td>
                    <td style={styles.td}>{fmt.date(quote.issue_date)}</td>
                    <td style={styles.td}>{fmt.date(quote.valid_until)}</td>
                    <td style={styles.td}>
                      {formatCommercialCurrency(
                        fmt.currency(quote.total_amount, quote.currency),
                        quote.currency,
                        locale,
                      )}
                    </td>
                    <td style={styles.td}>
                      <div style={styles.actions}>
                        {quote.status === "draft" ? (
                          <PermissionGuard code="commercial:quotes:update"><Link href={`/quotes/${quote.id}/edit`} style={styles.actionButton}>
                            {common("actions.edit")}
                          </Link></PermissionGuard>
                        ) : null}
                        <PermissionGuard code="commercial:quotes:delete"><button
                          type="button"
                          style={styles.deleteButton}
                          disabled={deletingId === quote.id || loadingImpactId === quote.id}
                          onClick={() => void handleDelete(quote.id)}
                        >
                          {deletingId === quote.id || loadingImpactId === quote.id
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
  );
}
