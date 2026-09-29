"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { deleteWorkCenter, getWorkCenters, getWorkCenterDeleteSummary } from "../api/work-centers-api";
import type { WorkCenterDeleteSummary, WorkCenterListItem } from "../types";
import {
  formatWorkCenterStatus,
  formatWorkCenterType,
  statusBadgeStyle,
  typeBadgeStyle,
} from "./work-center-utils";

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
    flexWrap: "nowrap" as const,
    gap: "8px",
    whiteSpace: "nowrap" as const,
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
    maxWidth: "480px",
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
  modalSummaryBox: {
    background: "var(--surface-muted)",
    border: "1px solid var(--border)",
    borderRadius: "6px",
    padding: "12px 16px",
    display: "grid",
    gap: "6px",
  },
  modalSummaryTitle: {
    fontSize: "13px",
    fontWeight: 700,
    color: "var(--text-muted)",
    margin: "0 0 4px",
  },
  modalSummaryItem: {
    fontSize: "13px",
    color: "var(--text-muted)",
    margin: 0,
  },
  modalWarning: {
    fontSize: "13px",
    fontWeight: 600,
    color: "var(--danger)",
    textAlign: "center" as const,
    margin: 0,
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

type DeleteTarget = { id: string; name: string };

export function WorkCentersList() {
  const t = useTranslations("production.workCenters");
  const tEnums = useTranslations();
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [workCenters, setWorkCenters] = useState<WorkCenterListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [deleteSummary, setDeleteSummary] = useState<WorkCenterDeleteSummary | null>(null);
  const [isSummaryLoading, setIsSummaryLoading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteModalError, setDeleteModalError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadWorkCenters = useCallback(async () => {
    if (!isMountedRef.current) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await getWorkCenters();
      if (isMountedRef.current) setWorkCenters(response);
    } catch (caughtError) {
      if (isMountedRef.current) setError(getApiErrorMessage(caughtError, messages));
    } finally {
      if (isMountedRef.current) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    void loadWorkCenters();
    return () => { isMountedRef.current = false; };
  }, [loadWorkCenters]);

  async function handleDeleteClick(id: string, name: string) {
    setDeleteTarget({ id, name });
    setDeleteSummary(null);
    setDeleteModalError(null);
    setIsSummaryLoading(true);
    try {
      const summary = await getWorkCenterDeleteSummary(id);
      if (isMountedRef.current) setDeleteSummary(summary);
    } catch (caughtError) {
      if (isMountedRef.current) {
        setDeleteModalError(getApiErrorMessage(caughtError, messages));
      }
    } finally {
      if (isMountedRef.current) setIsSummaryLoading(false);
    }
  }

  function handleCancelDelete() {
    if (isDeleting) return;
    setDeleteTarget(null);
    setDeleteSummary(null);
    setDeleteModalError(null);
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    setIsDeleting(true);
    setDeleteModalError(null);
    try {
      await deleteWorkCenter(deleteTarget.id);
      if (isMountedRef.current) {
        setDeleteTarget(null);
        setDeleteSummary(null);
        setSuccessMessage(t("deleteSuccess"));
        await loadWorkCenters();
      }
    } catch (caughtError) {
      if (isMountedRef.current) {
        setDeleteModalError(getApiErrorMessage(caughtError, messages));
      }
    } finally {
      if (isMountedRef.current) setIsDeleting(false);
    }
  }

  const hasRelatedData = deleteSummary
    ? deleteSummary.production_orders_count > 0 ||
      deleteSummary.shifts_count > 0 ||
      deleteSummary.shift_reports_count > 0 ||
      deleteSummary.downtime_records_count > 0 ||
      deleteSummary.waste_records_count > 0 ||
      deleteSummary.production_outputs_count > 0
    : false;

  return (
    <>
      {deleteTarget ? (
        <div style={styles.backdrop} onClick={!isDeleting ? handleCancelDelete : undefined}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalIcon}>!</div>
            <h2 style={styles.modalTitle}>{t("deleteConfirmTitle")}</h2>

            {isSummaryLoading ? (
              <p style={styles.modalBody}>{messages("loading.default")}</p>
            ) : (
              <>
                <p style={styles.modalBody}>{t("deleteConfirmMessage")}</p>

                {hasRelatedData && deleteSummary ? (
                  <div style={styles.modalSummaryBox}>
                    <p style={styles.modalSummaryTitle}>{t("deleteRelatedSummary")}</p>
                    {deleteSummary.production_orders_count > 0 ? (
                      <p style={styles.modalSummaryItem}>
                        {t("deleteRelatedProductionOrders", { count: deleteSummary.production_orders_count })}
                      </p>
                    ) : null}
                    {deleteSummary.shifts_count > 0 ? (
                      <p style={styles.modalSummaryItem}>
                        {t("deleteRelatedShifts", { count: deleteSummary.shifts_count })}
                      </p>
                    ) : null}
                    {deleteSummary.shift_reports_count > 0 ? (
                      <p style={styles.modalSummaryItem}>
                        {t("deleteRelatedShiftReports", { count: deleteSummary.shift_reports_count })}
                      </p>
                    ) : null}
                    {deleteSummary.downtime_records_count > 0 ? (
                      <p style={styles.modalSummaryItem}>
                        {t("deleteRelatedDowntime", { count: deleteSummary.downtime_records_count })}
                      </p>
                    ) : null}
                    {deleteSummary.waste_records_count > 0 ? (
                      <p style={styles.modalSummaryItem}>
                        {t("deleteRelatedWaste", { count: deleteSummary.waste_records_count })}
                      </p>
                    ) : null}
                    {deleteSummary.production_outputs_count > 0 ? (
                      <p style={styles.modalSummaryItem}>
                        {t("deleteRelatedOutputs", { count: deleteSummary.production_outputs_count })}
                      </p>
                    ) : null}
                  </div>
                ) : null}

                <p style={styles.modalWarning}>{t("deleteWarning")}</p>
              </>
            )}

            {deleteModalError ? (
              <div style={sharedStyles.error} role="alert">{deleteModalError}</div>
            ) : null}

            <div style={styles.modalActions}>
              <button
                type="button"
                style={styles.modalCancelButton}
                onClick={handleCancelDelete}
                disabled={isDeleting}
              >
                {t("deleteCancelButton")}
              </button>
              <button
                type="button"
                style={styles.modalDeleteButton}
                onClick={() => void handleConfirmDelete()}
                disabled={isSummaryLoading || isDeleting}
              >
                {isDeleting ? messages("loading.deleting") : t("deleteConfirmButton")}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <PageFrame
        section="Production"
        title={t("listTitle")}
        subtitle={t("subtitle")}
        action={
          <Link href="/work-centers/new" style={sharedStyles.button}>
            {t("newButton")}
          </Link>
        }
      >
        {isLoading ? (
          <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
            {t("loading")}
          </div>
        ) : null}

        {!isLoading && successMessage ? (
          <div style={styles.success} role="status">{successMessage}</div>
        ) : null}

        {!isLoading && error ? (
          <div style={{ display: "grid", gap: "12px" }}>
            <div style={sharedStyles.error} role="alert">{error}</div>
            <button
              style={{ ...sharedStyles.secondaryButton, width: "fit-content" }}
              type="button"
              onClick={() => void loadWorkCenters()}
            >
              {common("actions.retry")}
            </button>
          </div>
        ) : null}

        {!isLoading && !error && workCenters.length === 0 ? (
          <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
            <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("empty")}</h2>
            <p style={{ margin: "0 0 18px" }}>{t("createFirst")}</p>
            <Link href="/work-centers/new" style={sharedStyles.button}>
              {t("createButton")}
            </Link>
          </section>
        ) : null}

        {!isLoading && !error && workCenters.length > 0 ? (
          <section style={styles.panel} aria-label={t("listAria")}>
            <div style={styles.tableWrap}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>{t("fields.centerCode")}</th>
                    <th style={styles.th}>{t("fields.name")}</th>
                    <th style={styles.th}>{t("fields.centerType")}</th>
                    <th style={styles.th}>{t("fields.status")}</th>
                    <th style={styles.th}>{t("fields.location")}</th>
                    <th style={styles.th}>{t("fields.commissionedDate")}</th>
                    <th style={styles.th}>{t("fields.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {workCenters.map((wc) => (
                    <tr key={wc.id}>
                      <td style={styles.td}>{wc.code}</td>
                      <td style={styles.td}>
                        <Link href={`/work-centers/${wc.id}`} style={styles.link}>
                          {wc.name}
                        </Link>
                      </td>
                      <td style={styles.td}>
                        <span style={typeBadgeStyle(wc.center_type)}>
                          {formatWorkCenterType(wc.center_type, tEnums)}
                        </span>
                      </td>
                      <td style={styles.td}>
                        <span style={statusBadgeStyle(wc.status)}>
                          {formatWorkCenterStatus(wc.status, tEnums)}
                        </span>
                      </td>
                      <td style={styles.td}>{displayValue(wc.location)}</td>
                      <td style={styles.td}>
                        {wc.commissioned_date ? fmt.date(wc.commissioned_date) : displayValue(null)}
                      </td>
                      <td style={styles.td}>
                        <div style={styles.actions}>
                          <Link
                            href={`/work-centers/${wc.id}/edit`}
                            style={styles.actionButton}
                          >
                            {common("actions.edit")}
                          </Link>
                          <button
                            type="button"
                            style={styles.deleteButton}
                            disabled={isDeleting && deleteTarget?.id === wc.id}
                            onClick={() => void handleDeleteClick(wc.id, wc.name)}
                          >
                            {common("actions.delete")}
                          </button>
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
    </>
  );
}
