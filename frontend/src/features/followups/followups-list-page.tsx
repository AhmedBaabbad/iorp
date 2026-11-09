"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue, optionalText, toDatetimeLocalValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type {
  EligibleFollowUpAssignee,
  FollowUp,
  FollowUpListFilters,
  FollowUpPriority,
  FollowUpStatus,
  FollowUpUpdateRequest,
} from "@/types/followups";
import { FollowUpPriorityBadge, FollowUpStatusBadge } from "./followup-badges";
import {
  cancelFollowUp,
  completeFollowUp,
  deleteFollowUp,
  getEligibleAssignees,
  listFollowUps,
  reopenFollowUp,
  updateFollowUp,
} from "./followup-api";

const editPriorityOptions: FollowUpPriority[] = ["low", "medium", "high", "urgent"];

type EditValues = {
  due_date: string;
  priority: FollowUpPriority;
  reason: string;
  notes: string;
  assigned_user_id: string;
};

function toEditValues(followUp: FollowUp): EditValues {
  return {
    due_date: toDatetimeLocalValue(new Date(followUp.due_date)),
    priority: followUp.priority,
    reason: followUp.reason,
    notes: followUp.notes ?? "",
    assigned_user_id: followUp.assigned_user?.id ?? "",
  };
}

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
  },
  tabs: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
    marginBottom: "16px",
  },
  tabButton: {
    border: "1px solid var(--border-strong)",
    borderRadius: "999px",
    background: "var(--surface)",
    color: "var(--text-muted)",
    cursor: "pointer",
    fontSize: "13px",
    fontWeight: 700,
    padding: "8px 14px",
  },
  tabButtonActive: {
    background: "var(--text)",
    borderColor: "var(--border-strong)",
    color: "var(--surface)",
  },
  filtersRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "10px",
    marginBottom: "16px",
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
  editPanel: {
    background: "var(--surface-muted)",
    borderRadius: "8px",
    display: "grid",
    gap: "14px",
    padding: "16px",
  },
  editGrid: {
    display: "grid",
    gap: "14px",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
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
    flexWrap: "wrap",
    gap: "6px",
  },
  actionButton: {
    ...sharedStyles.secondaryButton,
    minHeight: "30px",
    padding: "5px 10px",
    fontSize: "12px",
  },
  dangerButton: {
    ...sharedStyles.dangerButton,
    minHeight: "30px",
    padding: "5px 10px",
    fontSize: "12px",
  },
  pagination: {
    display: "flex", flexWrap: "wrap",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    padding: "16px",
  },
};

type TabKey = "mine" | "today" | "upcoming" | "overdue" | "completed" | "cancelled" | "all";

const statusOptions: FollowUpStatus[] = ["pending", "in_progress", "completed", "cancelled"];

function StatusOptionLabel({ status }: { status: FollowUpStatus }) {
  const tEnums = useTranslations();
  return <>{tEnums(`enums.followUp.status.${status}`)}</>;
}

function buildTabFilters(tab: TabKey): FollowUpListFilters {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const endOfToday = new Date(startOfToday.getTime() + 24 * 60 * 60 * 1000 - 1);
  const in7Days = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);

  switch (tab) {
    case "today":
      return { scope: "mine", due_from: startOfToday.toISOString(), due_to: endOfToday.toISOString() };
    case "upcoming":
      return { scope: "mine", due_from: now.toISOString(), due_to: in7Days.toISOString() };
    case "overdue":
      return { scope: "mine", overdue: true };
    case "completed":
      return { scope: "mine", status: "completed" };
    case "cancelled":
      return { scope: "mine", status: "cancelled" };
    case "all":
      return { scope: "all" };
    case "mine":
    default:
      return { scope: "mine" };
  }
}

const VALID_TABS: TabKey[] = ["mine", "today", "upcoming", "overdue", "completed", "cancelled", "all"];

function isTabKey(value: string | null): value is TabKey {
  return value !== null && (VALID_TABS as string[]).includes(value);
}

export function FollowUpsListPage() {
  const t = useTranslations("commercial.followUps");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const searchParams = useSearchParams();

  const canUpdate = usePermission("commercial:follow_ups:update");
  const canCancel = usePermission("commercial:follow_ups:cancel");
  const canReopen = usePermission("commercial:follow_ups:reopen");
  const canDelete = usePermission("commercial:follow_ups:delete");
  const canComplete = usePermission("commercial:follow_ups:complete");
  const canAssign = usePermission("commercial:follow_ups:assign");

  const initialTab = searchParams.get("tab");
  const [tab, setTab] = useState<TabKey>(isTabKey(initialTab) ? initialTab : "mine");
  const [statusFilter, setStatusFilter] = useState<FollowUpStatus | "">("");
  const [unassignedOnly, setUnassignedOnly] = useState(
    searchParams.get("unassigned") === "true",
  );
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [items, setItems] = useState<FollowUp[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<EditValues | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [eligibleAssignees, setEligibleAssignees] = useState<EligibleFollowUpAssignee[]>([]);
  const isMountedRef = useRef(true);

  const loadFollowUps = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const filters: FollowUpListFilters = {
        ...buildTabFilters(tab),
        ...(statusFilter ? { status: statusFilter } : {}),
        ...(search ? { search } : {}),
        ...(unassignedOnly ? { scope: "all", unassigned: true } : {}),
        page,
        page_size: pageSize,
      };
      const response = await listFollowUps(filters);
      if (isMountedRef.current) {
        setItems(response.items);
        setTotal(response.total);
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
  }, [tab, statusFilter, search, unassignedOnly, page, messages]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadFollowUps();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadFollowUps]);

  useEffect(() => {
    if (!canAssign) {
      return;
    }
    let cancelled = false;
    getEligibleAssignees()
      .then((data) => {
        if (!cancelled) setEligibleAssignees(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [canAssign]);

  function selectTab(nextTab: TabKey) {
    setTab(nextTab);
    setStatusFilter("");
    setPage(1);
  }

  function startEdit(followUp: FollowUp) {
    setEditingId(followUp.id);
    setEditValues(toEditValues(followUp));
    setEditError(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditValues(null);
    setEditError(null);
  }

  function updateEditField<TField extends keyof EditValues>(field: TField, value: EditValues[TField]) {
    setEditValues((current) => (current ? { ...current, [field]: value } : current));
  }

  async function saveEdit(followUpId: string) {
    if (!editValues) return;
    setIsSavingEdit(true);
    setEditError(null);
    try {
      const payload: FollowUpUpdateRequest = {
        due_date: new Date(editValues.due_date).toISOString(),
        priority: editValues.priority,
        reason: editValues.reason.trim(),
        notes: optionalText(editValues.notes),
        ...(canAssign ? { assigned_user_id: optionalText(editValues.assigned_user_id) } : {}),
      };
      await updateFollowUp(followUpId, payload);
      cancelEdit();
      await loadFollowUps();
    } catch (caughtError) {
      setEditError(getApiErrorMessage(caughtError, messages));
    } finally {
      if (isMountedRef.current) {
        setIsSavingEdit(false);
      }
    }
  }

  async function runAction(followUpId: string, action: () => Promise<FollowUp>) {
    setActionId(followUpId);
    setError(null);
    try {
      await action();
      await loadFollowUps();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      if (isMountedRef.current) {
        setActionId(null);
      }
    }
  }

  async function handleDelete(followUpId: string) {
    setActionId(followUpId);
    setError(null);
    try {
      await deleteFollowUp(followUpId);
      await loadFollowUps();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      if (isMountedRef.current) {
        setActionId(null);
      }
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <PageFrame title={t("listTitle")} subtitle={t("subtitle")} section="Commercial">
      <div style={styles.tabs} role="tablist">
        {VALID_TABS.map((tabKey) => (
          <button
            key={tabKey}
            type="button"
            role="tab"
            aria-selected={tab === tabKey}
            style={{ ...styles.tabButton, ...(tab === tabKey ? styles.tabButtonActive : {}) }}
            onClick={() => selectTab(tabKey)}
          >
            {t(`tabs.${tabKey === "mine" ? "myFollowUps" : tabKey}`)}
          </button>
        ))}
      </div>

      <div style={styles.filtersRow}>
        <input
          style={{ ...sharedStyles.input, maxWidth: "280px" }}
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder={t("filters.searchPlaceholder")}
        />
        <select
          style={{ ...sharedStyles.input, maxWidth: "200px" }}
          value={statusFilter}
          onChange={(event) => {
            setStatusFilter(event.target.value as FollowUpStatus | "");
            setPage(1);
          }}
        >
          <option value="">{t("filters.allStatuses")}</option>
          {statusOptions.map((status) => (
            <option key={status} value={status}>
              <StatusOptionLabel status={status} />
            </option>
          ))}
        </select>
        {canAssign ? (
          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("filters.assignmentStatus")}</span>
            <select
              style={{ ...sharedStyles.input, maxWidth: "220px" }}
              value={unassignedOnly ? "unassigned" : "all"}
              onChange={(event) => {
                setUnassignedOnly(event.target.value === "unassigned");
                setPage(1);
              }}
            >
              <option value="all">{t("filters.assignmentStatus")}</option>
              <option value="unassigned">{t("filters.unassignedOnly")}</option>
            </select>
          </label>
        ) : null}
      </div>

      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{t("loading")}</div>
      ) : null}

      {!isLoading && error ? (
        <div style={{ display: "grid", gap: "12px" }}>
          <div style={sharedStyles.error} role="alert">
            {error}
          </div>
          <button
            style={{ ...sharedStyles.secondaryButton, width: "fit-content" }}
            type="button"
            onClick={() => void loadFollowUps()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && items.length === 0 ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{t("empty")}</div>
      ) : null}

      {!isLoading && !error && items.length > 0 ? (
        <section style={styles.panel} aria-label={t("listTitle")}>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t("fields.customer")}</th>
                  <th style={styles.th}>{t("fields.reason")}</th>
                  <th style={styles.th}>{t("fields.assignedUser")}</th>
                  <th style={styles.th}>{t("fields.dueDate")}</th>
                  <th style={styles.th}>{t("fields.priority")}</th>
                  <th style={styles.th}>{t("fields.status")}</th>
                  <th style={styles.th}>{t("fields.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((followUp) => (
                  <tr key={followUp.id}>
                    <td style={styles.td}>
                      <Link
                        href={`/customers/${followUp.customer.id}#follow-ups-title`}
                        style={styles.link}
                      >
                        {followUp.customer.customer_code} - {followUp.customer.customer_name}
                      </Link>
                    </td>
                    <td style={styles.td}>{followUp.reason}</td>
                    <td style={styles.td}>
                      {followUp.is_unassigned
                        ? t("unassigned")
                        : displayValue(followUp.assigned_user?.full_name ?? null)}
                      {followUp.is_unassigned &&
                      (followUp.status === "pending" || followUp.status === "in_progress") ? (
                        <div style={sharedStyles.modalWarning}>
                          {t("needsReassignment")}
                        </div>
                      ) : null}
                    </td>
                    <td style={styles.td}>{fmt.dateTime(followUp.due_date)}</td>
                    <td style={styles.td}>
                      <FollowUpPriorityBadge priority={followUp.priority} />
                    </td>
                    <td style={styles.td}>
                      <FollowUpStatusBadge status={followUp.status} isOverdue={followUp.is_overdue} />
                    </td>
                    <td style={styles.td}>
                      <div style={styles.actions}>
                        {(followUp.status === "pending" || followUp.status === "in_progress") &&
                        canComplete ? (
                          <button
                            type="button"
                            style={styles.actionButton}
                            disabled={actionId === followUp.id}
                            onClick={() =>
                              void runAction(followUp.id, () => completeFollowUp(followUp.id))
                            }
                          >
                            {t("actions.complete")}
                          </button>
                        ) : null}
                        {(followUp.status === "completed" || followUp.status === "cancelled") &&
                        canReopen ? (
                          <button
                            type="button"
                            style={styles.actionButton}
                            disabled={actionId === followUp.id}
                            onClick={() =>
                              void runAction(followUp.id, () => reopenFollowUp(followUp.id))
                            }
                          >
                            {t("actions.reopen")}
                          </button>
                        ) : null}
                        {(followUp.status === "pending" || followUp.status === "in_progress") &&
                        canCancel ? (
                          <button
                            type="button"
                            style={styles.actionButton}
                            disabled={actionId === followUp.id}
                            onClick={() =>
                              void runAction(followUp.id, () => cancelFollowUp(followUp.id))
                            }
                          >
                            {t("actions.cancel")}
                          </button>
                        ) : null}
                        {canUpdate ? (
                          <button
                            type="button"
                            style={styles.actionButton}
                            disabled={actionId === followUp.id}
                            onClick={() => startEdit(followUp)}
                          >
                            {t("actions.edit")}
                          </button>
                        ) : null}
                        {canAssign &&
                        followUp.is_unassigned &&
                        (followUp.status === "pending" || followUp.status === "in_progress") ? (
                          <button
                            type="button"
                            style={styles.actionButton}
                            disabled={actionId === followUp.id}
                            onClick={() => startEdit(followUp)}
                          >
                            {t("actions.reassign")}
                          </button>
                        ) : null}
                        {canDelete ? (
                          <button
                            type="button"
                            style={styles.dangerButton}
                            disabled={actionId === followUp.id}
                            onClick={() => void handleDelete(followUp.id)}
                          >
                            {t("actions.delete")}
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
                {editingId && editValues
                  ? items
                      .filter((followUp) => followUp.id === editingId)
                      .map((followUp) => (
                        <tr key={`${followUp.id}-edit`}>
                          <td style={styles.td} colSpan={7}>
                            <div style={styles.editPanel}>
                              <div style={styles.editGrid}>
                                <label style={sharedStyles.field}>
                                  <span style={sharedStyles.label}>{t("fields.dueDate")}</span>
                                  <input
                                    style={sharedStyles.input}
                                    type="datetime-local"
                                    value={editValues.due_date}
                                    onChange={(event) => updateEditField("due_date", event.target.value)}
                                    disabled={isSavingEdit}
                                  />
                                </label>
                                <label style={sharedStyles.field}>
                                  <span style={sharedStyles.label}>{t("fields.priority")}</span>
                                  <select
                                    style={sharedStyles.input}
                                    value={editValues.priority}
                                    onChange={(event) =>
                                      updateEditField("priority", event.target.value as FollowUpPriority)
                                    }
                                    disabled={isSavingEdit}
                                  >
                                    {editPriorityOptions.map((priority) => (
                                      <option key={priority} value={priority}>
                                        <PriorityOptionLabel priority={priority} />
                                      </option>
                                    ))}
                                  </select>
                                </label>
                                <label style={sharedStyles.field}>
                                  <span style={sharedStyles.label}>{t("fields.reason")}</span>
                                  <input
                                    style={sharedStyles.input}
                                    value={editValues.reason}
                                    onChange={(event) => updateEditField("reason", event.target.value)}
                                    maxLength={255}
                                    disabled={isSavingEdit}
                                  />
                                </label>
                                {canAssign ? (
                                  <label style={sharedStyles.field}>
                                    <span style={sharedStyles.label}>{t("selectAssignee")}</span>
                                    <select
                                      style={sharedStyles.input}
                                      value={editValues.assigned_user_id}
                                      onChange={(event) =>
                                        updateEditField("assigned_user_id", event.target.value)
                                      }
                                      disabled={isSavingEdit}
                                    >
                                      <option value="">{t("selectAssignee")}</option>
                                      {eligibleAssignees.map((assignee) => (
                                        <option key={assignee.id} value={assignee.id}>
                                          {assignee.roles[0]?.name
                                            ? `${assignee.full_name} — ${assignee.roles[0].name}`
                                            : assignee.full_name}
                                        </option>
                                      ))}
                                    </select>
                                  </label>
                                ) : null}
                              </div>
                              <label style={sharedStyles.field}>
                                <span style={sharedStyles.label}>{t("fields.notes")}</span>
                                <textarea
                                  style={sharedStyles.textarea}
                                  value={editValues.notes}
                                  onChange={(event) => updateEditField("notes", event.target.value)}
                                  disabled={isSavingEdit}
                                />
                              </label>
                              {editError ? (
                                <div style={sharedStyles.error} role="alert">
                                  {editError}
                                </div>
                              ) : null}
                              <div style={styles.actions}>
                                <button
                                  type="button"
                                  style={sharedStyles.button}
                                  disabled={isSavingEdit}
                                  onClick={() => void saveEdit(followUp.id)}
                                >
                                  {isSavingEdit ? messages("loading.saving") : common("actions.save")}
                                </button>
                                <button
                                  type="button"
                                  style={sharedStyles.secondaryButton}
                                  disabled={isSavingEdit}
                                  onClick={cancelEdit}
                                >
                                  {t("actions.cancelAction")}
                                </button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      ))
                  : null}
              </tbody>
            </table>
          </div>
          <div style={styles.pagination}>
            <span style={sharedStyles.meta}>
              {common("pagination.showing", {
                from: (page - 1) * pageSize + 1,
                to: Math.min(page * pageSize, total),
                total,
              })}
            </span>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
              <button
                type="button"
                style={sharedStyles.secondaryButton}
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                {common("pagination.previous")}
              </button>
              <button
                type="button"
                style={sharedStyles.secondaryButton}
                disabled={page >= totalPages}
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              >
                {common("pagination.next")}
              </button>
            </div>
          </div>
        </section>
      ) : null}
    </PageFrame>
  );
}

function PriorityOptionLabel({ priority }: { priority: FollowUpPriority }) {
  const tEnums = useTranslations();
  return <>{tEnums(`enums.followUp.priority.${priority}`)}</>;
}
