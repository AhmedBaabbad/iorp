"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth";
import { useEnumLabel } from "@/i18n/enum-helpers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import {
  deleteWorkforceMember,
  getWorkforceMemberDeletionImpact,
  getWorkforceMembers,
} from "../api/workforce-api";
import type {
  EmploymentType,
  WorkforceMemberDeletionImpact,
  WorkforceMemberFilters,
  WorkforceMemberListItem,
  WorkforceMemberStatus,
  WorkerType,
} from "../types";
import { WorkforceMemberStatusBadge } from "./WorkforceMemberStatusBadge";
import { WorkforceMemberTypeBadge } from "./WorkforceMemberTypeBadge";

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
  },
  filters: {
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
    marginBottom: "16px",
  },
  tableWrap: { overflowX: "auto" },
  table: { width: "100%", borderCollapse: "collapse" },
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
  link: { color: "var(--accent-strong)", fontWeight: 700, textDecoration: "none" },
  actions: { display: "flex", flexWrap: "nowrap", gap: "8px", whiteSpace: "nowrap" },
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
    marginBottom: "16px",
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

const statuses: WorkforceMemberStatus[] = ["active", "inactive", "suspended", "terminated"];
const employmentTypes: EmploymentType[] = ["employee", "contractor", "temporary"];
const workerTypes: WorkerType[] = [
  "factory_manager",
  "production_manager",
  "supervisor",
  "operator",
  "technician",
  "maintenance_technician",
  "helper",
  "quality_inspector",
  "warehouse_staff",
  "logistics_coordinator",
  "sales_manager",
  "sales_rep",
  "procurement_officer",
  "hr_officer",
  "accountant",
  "safety_officer",
  "admin_support",
];

export function WorkforceMembersList() {
  const t = useTranslations("workforce.members");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const enumLabel = useEnumLabel();
  const canCreate = usePermission("workforce:members:create");
  const canUpdate = usePermission("workforce:members:update");
  const canDelete = usePermission("workforce:members:delete");
  const [members, setMembers] = useState<WorkforceMemberListItem[]>([]);
  const [filters, setFilters] = useState<WorkforceMemberFilters>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [memberToDelete, setMemberToDelete] = useState<WorkforceMemberListItem | null>(null);
  const [deletionImpact, setDeletionImpact] = useState<WorkforceMemberDeletionImpact | null>(null);
  const [isImpactLoading, setIsImpactLoading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadMembers = useCallback(async () => {
    if (!isMountedRef.current) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await getWorkforceMembers(filters);
      if (isMountedRef.current) setMembers(response);
    } catch (caughtError) {
      if (isMountedRef.current) setError(getApiErrorMessage(caughtError, messages));
    } finally {
      if (isMountedRef.current) setIsLoading(false);
    }
  }, [filters, messages]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadMembers();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadMembers]);

  async function handleDeleteClick(member: WorkforceMemberListItem) {
    setMemberToDelete(member);
    setDeletionImpact(null);
    setDeleteError(null);
    setSuccessMessage(null);
    setIsImpactLoading(true);
    try {
      const impact = await getWorkforceMemberDeletionImpact(member.id);
      if (isMountedRef.current) setDeletionImpact(impact);
    } catch (caughtError) {
      if (isMountedRef.current) setDeleteError(getApiErrorMessage(caughtError, messages));
    } finally {
      if (isMountedRef.current) setIsImpactLoading(false);
    }
  }

  function handleCancelDelete() {
    if (isDeleting) return;
    setMemberToDelete(null);
    setDeletionImpact(null);
    setDeleteError(null);
  }

  async function handleConfirmDelete() {
    if (!memberToDelete) return;
    setIsDeleting(true);
    setSuccessMessage(null);
    setDeleteError(null);
    try {
      await deleteWorkforceMember(memberToDelete.id);
      if (isMountedRef.current) {
        setMemberToDelete(null);
        setDeletionImpact(null);
        setSuccessMessage(t("deleteSuccess"));
        await loadMembers();
      }
    } catch {
      if (isMountedRef.current) {
        setDeleteError(t("deleteError"));
      }
    } finally {
      if (isMountedRef.current) setIsDeleting(false);
    }
  }

  return (
    <>
      {memberToDelete ? (
        <div style={styles.backdrop} onClick={!isDeleting ? handleCancelDelete : undefined}>
          <div style={styles.modal} onClick={(event) => event.stopPropagation()}>
            <div style={styles.modalIcon}>!</div>
            <h2 style={styles.modalTitle}>{t("deleteConfirmTitle")}</h2>
            {isImpactLoading ? (
              <p style={styles.modalBody}>{messages("loading.default")}</p>
            ) : (
              <>
                <p style={styles.modalBody}>
                  {t("deleteConfirmMessage", { name: memberToDelete.full_name })}
                </p>
                <p style={styles.modalWarning}>{t("deleteWarning")}</p>
              </>
            )}
            {deleteError ? (
              <div style={sharedStyles.error} role="alert">
                {deleteError}
              </div>
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
                disabled={isImpactLoading || isDeleting || deletionImpact?.is_blocked === true}
              >
                {isDeleting ? messages("loading.deleting") : t("deleteConfirmButton")}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <PageFrame
        section="Workforce"
        title={t("listTitle")}
        subtitle={t("subtitle")}
        action={
          canCreate ? (
            <Link href="/workforce/new" style={sharedStyles.button}>
              {t("newButton")}
            </Link>
          ) : null
        }
      >
        <div style={styles.filters}>
          <select
            style={sharedStyles.input}
            value={filters.worker_type ?? ""}
            onChange={(event) =>
              setFilters((current) => ({ ...current, worker_type: event.target.value as WorkerType | "" }))
            }
            aria-label={t("fields.workerType")}
          >
            <option value="">{t("filters.allWorkerTypes")}</option>
            {workerTypes.map((value) => (
              <option key={value} value={value}>
                {enumLabel("workforceMember", "workerType", value)}
              </option>
            ))}
          </select>
          <select
            style={sharedStyles.input}
            value={filters.employment_type ?? ""}
            onChange={(event) =>
              setFilters((current) => ({ ...current, employment_type: event.target.value as EmploymentType | "" }))
            }
            aria-label={t("fields.employmentType")}
          >
            <option value="">{t("filters.allEmploymentTypes")}</option>
            {employmentTypes.map((value) => (
              <option key={value} value={value}>
                {enumLabel("workforceMember", "employmentType", value)}
              </option>
            ))}
          </select>
          <select
            style={sharedStyles.input}
            value={filters.status ?? ""}
            onChange={(event) =>
              setFilters((current) => ({ ...current, status: event.target.value as WorkforceMemberStatus | "" }))
            }
            aria-label={t("fields.status")}
          >
            <option value="">{t("filters.allStatuses")}</option>
            {statuses.map((value) => (
              <option key={value} value={value}>
                {enumLabel("workforceMember", "status", value)}
              </option>
            ))}
          </select>
        </div>

      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{t("loading")}</div>
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
            onClick={() => void loadMembers()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && members.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("empty")}</h2>
          <p style={{ margin: "0 0 18px" }}>{t("createFirst")}</p>
          {canCreate ? (
            <Link href="/workforce/new" style={sharedStyles.button}>
              {t("createButton")}
            </Link>
          ) : null}
        </section>
      ) : null}

      {!isLoading && !error && members.length > 0 ? (
        <section style={styles.panel} aria-label={t("listAria")}>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t("fields.employeeCode")}</th>
                  <th style={styles.th}>{t("fields.fullName")}</th>
                  <th style={styles.th}>{t("fields.workerType")}</th>
                  <th style={styles.th}>{t("fields.employmentType")}</th>
                  <th style={styles.th}>{t("fields.status")}</th>
                  <th style={styles.th}>{t("fields.phone")}</th>
                  <th style={styles.th}>{t("fields.isSystemUser")}</th>
                  <th style={styles.th}>{t("fields.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {members.map((member) => (
                  <tr key={member.id}>
                    <td style={styles.td}>{member.employee_code}</td>
                    <td style={styles.td}>
                      <Link href={`/workforce/${member.id}`} style={styles.link}>
                        {member.full_name}
                      </Link>
                    </td>
                    <td style={styles.td}>
                      <WorkforceMemberTypeBadge workerType={member.worker_type} />
                    </td>
                    <td style={styles.td}>
                      {enumLabel("workforceMember", "employmentType", member.employment_type)}
                    </td>
                    <td style={styles.td}>
                      <WorkforceMemberStatusBadge status={member.status} />
                    </td>
                    <td style={styles.td}>{displayValue(member.phone)}</td>
                    <td style={styles.td}>
                      {member.is_system_user ? t("systemUserYes") : t("systemUserNo")}
                    </td>
                    <td style={styles.td}>
                      <div style={styles.actions}>
                        <Link href={`/workforce/${member.id}`} style={styles.actionButton}>
                          {common("actions.view")}
                        </Link>
                        {canUpdate ? (
                          <Link href={`/workforce/${member.id}/edit`} style={styles.actionButton}>
                            {common("actions.edit")}
                          </Link>
                        ) : null}
                        {canDelete ? (
                          <button
                            type="button"
                            style={styles.deleteButton}
                            disabled={isDeleting && memberToDelete?.id === member.id}
                            onClick={() => void handleDeleteClick(member)}
                          >
                            {isDeleting && memberToDelete?.id === member.id
                              ? messages("loading.deleting")
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
    </>
  );
}
