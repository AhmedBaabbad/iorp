"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { deleteShift, getShiftDeletionImpact, getShifts } from "../api/shifts-api";
import type { ShiftDeletionImpact, ShiftListItem } from "../types";
import {
  formatShiftStatus,
  formatShiftType,
  formatTimeRange,
  statusBadgeStyle,
  typeBadgeStyle,
} from "./shift-utils";
import { usePermission } from "@/features/auth/permission-hooks";
import { P } from "@/lib/production-permissions";


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
  muted: {
    color: "var(--text-muted)",
    fontSize: "13px",
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

export function ShiftsList() {
  const t = useTranslations("production.shifts");
  const canCreate = usePermission(P.SHIFTS_CREATE);
  const canUpdate = usePermission(P.SHIFTS_UPDATE);
  const canDelete = usePermission(P.SHIFTS_DELETE);
  const tEnums = useTranslations();
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const [shifts, setShifts] = useState<ShiftListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [loadingImpactId, setLoadingImpactId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<{ id: string; impact: ShiftDeletionImpact } | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadShifts = useCallback(async () => {
    if (!isMountedRef.current) return;
    setIsLoading(true);
    setError(null);
    try {
      const shiftsResponse = await getShifts();
      if (isMountedRef.current) {
        setShifts(shiftsResponse);
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

  useEffect(() => {
    isMountedRef.current = true;
    void loadShifts();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadShifts]);

  async function handleDelete(shiftId: string) {
    setLoadingImpactId(shiftId);
    setDeleteError(null);
    try {
      const impact = await getShiftDeletionImpact(shiftId);
      if (isMountedRef.current) {
        setPendingDelete({ id: shiftId, impact });
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
      await deleteShift(idToDelete);
      if (isMountedRef.current) {
        setSuccessMessage(t("deleteSuccess"));
        await loadShifts();
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
    <PageFrame
      section="Production"
      title={t("listTitle")}
      subtitle={t("subtitle")}
      action={canCreate ? (
        <Link href="/shifts/new" style={sharedStyles.button}>
          {t("newButton")}
        </Link>
      ) : undefined}
    >
      {pendingDelete ? (
        <div
          style={styles.backdrop}
          onClick={pendingDelete.impact.is_blocked ? handleCancelDelete : undefined}
        >
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalIcon}>
              {pendingDelete.impact.is_blocked ? "🚫" : "🗑️"}
            </div>
            <h2 style={styles.modalTitle}>
              {pendingDelete.impact.is_blocked
                ? t("delete.blockedTitle")
                : t("delete.confirmTitle")}
            </h2>

            {pendingDelete.impact.is_blocked ? (
              <>
                <p style={styles.modalBody}>{t("delete.blockedMessage")}</p>
                <ul style={{ margin: 0, padding: "0 0 0 20px", color: "var(--text-muted)", fontSize: "14px", lineHeight: "1.8" }}>
                  {pendingDelete.impact.production_orders > 0 ? (
                    <li>{t("delete.productionOrdersCount", { count: pendingDelete.impact.production_orders })}</li>
                  ) : null}
                </ul>
              </>
            ) : (
              <p style={styles.modalBody}>{t("delete.confirmMessage")}</p>
            )}

            {deleteError ? (
              <p style={{ margin: 0, color: "var(--danger)", fontSize: "13px", textAlign: "center" }}>
                {deleteError}
              </p>
            ) : null}

            <div style={styles.modalActions}>
              <button
                type="button"
                style={styles.modalCancelButton}
                onClick={handleCancelDelete}
              >
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

      <Link href="/shift-rosters" style={sharedStyles.secondaryButton}>{t("rosters")}</Link>
      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          {t("loading")}
        </div>
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
            onClick={() => void loadShifts()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && shifts.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("empty")}</h2>
          {canCreate ? <p style={{ margin: "0 0 18px" }}>{t("createFirst")}</p> : null}
          {canCreate ? (
            <Link href="/shifts/new" style={sharedStyles.button}>
              {t("createButton")}
            </Link>
          ) : null}
        </section>
      ) : null}

      {!isLoading && !error && shifts.length > 0 ? (
        <section style={styles.panel} aria-label={t("listAria")}>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t("fields.code")}</th>
                  <th style={styles.th}>{t("fields.name")}</th>
                  <th style={styles.th}>{t("fields.type")}</th>
                  <th style={styles.th}>{t("fields.time")}</th>
                  <th style={styles.th}>{t("fields.midnight")}</th>
                  <th style={styles.th}>{t("fields.status")}</th>
                  <th style={styles.th}>{t("fields.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {shifts.map((shift) => (
                  <tr key={shift.id}>
                    <td style={styles.td}>{shift.code}</td>
                    <td style={styles.td}>
                      <Link href={`/shifts/${shift.id}`} style={styles.link}>
                        {shift.name}
                      </Link>
                    </td>
                    <td style={styles.td}>
                      <span style={typeBadgeStyle(shift.shift_type)}>
                        {formatShiftType(shift.shift_type, tEnums)}
                      </span>
                    </td>
                    <td style={styles.td}>
                      {formatTimeRange(shift.start_time, shift.end_time)}
                    </td>
                    <td style={styles.td}>
                      {shift.crosses_midnight ? (
                        <span style={styles.muted}>{t("spansMidnight")}</span>
                      ) : (
                        <span style={styles.muted}>-</span>
                      )}
                    </td>
                    <td style={styles.td}>
                      <span style={statusBadgeStyle(shift.status)}>
                        {formatShiftStatus(shift.status, tEnums)}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <div style={styles.actions}>
                        {canUpdate ? (
                          <Link href={`/shifts/${shift.id}/edit`} style={styles.actionButton}>
                            {common("actions.edit")}
                          </Link>
                        ) : null}
                        {canDelete ? (
                          <button
                            type="button"
                            style={styles.deleteButton}
                            disabled={loadingImpactId === shift.id || deletingId === shift.id}
                            onClick={() => void handleDelete(shift.id)}
                          >
                            {loadingImpactId === shift.id || deletingId === shift.id
                              ? "..."
                              : common("actions.delete")}
                          </button>
                        ) : null}
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

