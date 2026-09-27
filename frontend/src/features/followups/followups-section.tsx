"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties, FormEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { SectionShell } from "@/components/layout/section-shell";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { useAuth, usePermission } from "@/features/auth";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type { EligibleFollowUpAssignee, FollowUp } from "@/types/followups";
import { FollowUpPriorityBadge, FollowUpStatusBadge } from "./followup-badges";
import {
  cancelFollowUp,
  completeFollowUp,
  createCustomerFollowUp,
  deleteFollowUp,
  getEligibleAssignees,
  listCustomerFollowUps,
  reopenFollowUp,
} from "./followup-api";
import {
  createDefaultFollowUpFormValues,
  toFollowUpCreateRequest,
  type FollowUpFormValues,
} from "./followup-form";

type CustomerFollowUpsSectionProps = {
  customerId: string;
  customerSalesOwnerId?: string | null;
};

const priorityOptions: FollowUpFormValues["priority"][] = ["low", "medium", "high", "urgent"];

const styles: Record<string, CSSProperties> = {
  form: {
    display: "grid",
    gap: "16px",
  },
  formGrid: {
    display: "grid",
    gap: "16px",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  },
  button: {
    ...sharedStyles.button,
    width: "fit-content",
  },
  compactButton: {
    ...sharedStyles.secondaryButton,
    minHeight: "36px",
    padding: "8px 12px",
    fontSize: "13px",
  },
  dangerButton: {
    ...sharedStyles.dangerButton,
    minHeight: "36px",
    padding: "8px 12px",
    fontSize: "13px",
  },
  actionsRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
    marginTop: "12px",
  },
  note: {
    color: "#52606d",
    fontSize: "13px",
    margin: 0,
  },
};

export function CustomerFollowUpsSection({
  customerId,
  customerSalesOwnerId,
}: CustomerFollowUpsSectionProps) {
  const t = useTranslations("commercial.followUps");
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const fmt = useFormatter();
  const { user } = useAuth();

  const canRead = usePermission("commercial:follow_ups:read");
  const canCreate = usePermission("commercial:follow_ups:create");
  const canUpdate = usePermission("commercial:follow_ups:update");
  const canDelete = usePermission("commercial:follow_ups:delete");
  const canComplete = usePermission("commercial:follow_ups:complete");
  const canAssign = usePermission("commercial:follow_ups:assign");
  const isEligibleAssignee = canUpdate && canRead;

  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [values, setValues] = useState<FollowUpFormValues>(createDefaultFollowUpFormValues);
  const [eligibleAssignees, setEligibleAssignees] = useState<EligibleFollowUpAssignee[]>([]);
  const [isLoadingAssignees, setIsLoadingAssignees] = useState(canAssign);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState(false);
  const isMountedRef = useRef(true);

  useEffect(() => {
    if (values.assigned_user_id) return;
    if (canAssign && customerSalesOwnerId) {
      setValues((current) => ({ ...current, assigned_user_id: customerSalesOwnerId }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canAssign, customerSalesOwnerId]);

  const loadFollowUps = useCallback(async () => {
    if (!isMountedRef.current || !canRead) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await listCustomerFollowUps(customerId);
      if (isMountedRef.current) {
        setFollowUps(response);
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
  }, [customerId, messages, canRead]);

  useEffect(() => {
    isMountedRef.current = true;
    if (canRead) {
      void loadFollowUps();
    } else {
      setIsLoading(false);
    }
    return () => {
      isMountedRef.current = false;
    };
  }, [loadFollowUps, canRead]);

  useEffect(() => {
    if (!canAssign) {
      return;
    }
    let cancelled = false;
    setIsLoadingAssignees(true);
    getEligibleAssignees()
      .then((data) => {
        if (!cancelled) setEligibleAssignees(data);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setIsLoadingAssignees(false);
      });
    return () => {
      cancelled = true;
    };
  }, [canAssign]);

  function updateField<TField extends keyof FollowUpFormValues>(
    field: TField,
    value: FollowUpFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (!user) {
      setFormError(messages("error.sessionExpired"));
      return;
    }

    setIsSubmitting(true);

    try {
      await createCustomerFollowUp(customerId, toFollowUpCreateRequest(values, canAssign));
      setValues(createDefaultFollowUpFormValues());
      await loadFollowUps();
      setFormSuccess(true);
    } catch (caughtError) {
      setFormError(getApiErrorMessage(caughtError, messages));
    } finally {
      if (isMountedRef.current) {
        setIsSubmitting(false);
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

  if (!canRead) {
    return null;
  }

  return (
    <>
    {formSuccess ? (
      <SuccessModal
        message={t("createSuccess")}
        okLabel={common("actions.ok")}
        onOk={() => setFormSuccess(false)}
      />
    ) : null}
    <SectionShell
      titleId="follow-ups-title"
      title={t("listTitle")}
      subtitle={t("subtitle")}
    >
      {canCreate || isEligibleAssignee ? (
      <form style={styles.form} onSubmit={handleSubmit}>
        <div style={styles.formGrid}>
          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>
              {t("fields.dueDate")}{" "}
              <span aria-hidden="true" style={{ color: "#be123c" }}>*</span>
            </span>
            <input
              style={sharedStyles.input}
              type="datetime-local"
              value={values.due_date}
              onChange={(event) => updateField("due_date", event.target.value)}
              disabled={isSubmitting}
              required
            />
          </label>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.priority")}</span>
            <select
              style={sharedStyles.input}
              value={values.priority}
              onChange={(event) =>
                updateField("priority", event.target.value as FollowUpFormValues["priority"])
              }
              disabled={isSubmitting}
            >
              {priorityOptions.map((priority) => (
                <option key={priority} value={priority}>
                  <PriorityOptionLabel priority={priority} />
                </option>
              ))}
            </select>
          </label>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>
              {t("fields.reason")}{" "}
              <span aria-hidden="true" style={{ color: "#be123c" }}>*</span>
            </span>
            <input
              style={sharedStyles.input}
              value={values.reason}
              onChange={(event) => updateField("reason", event.target.value)}
              maxLength={255}
              disabled={isSubmitting}
              required
            />
          </label>
        </div>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.notes")}</span>
          <textarea
            style={sharedStyles.textarea}
            value={values.notes}
            onChange={(event) => updateField("notes", event.target.value)}
            disabled={isSubmitting}
          />
        </label>

        {canAssign ? (
          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>
              {t("selectAssignee")}{" "}
              <span aria-hidden="true" style={{ color: "#be123c" }}>*</span>
            </span>
            {isLoadingAssignees ? (
              <p style={styles.note}>{t("loadingAssignees")}</p>
            ) : eligibleAssignees.length === 0 ? (
              <p style={styles.note}>{t("noEligibleAssignees")}</p>
            ) : (
              <select
                style={sharedStyles.input}
                value={values.assigned_user_id}
                onChange={(event) => updateField("assigned_user_id", event.target.value)}
                disabled={isSubmitting}
                required
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
            )}
            {customerSalesOwnerId ? (
              <span style={styles.note}>{t("defaultFromSalesOwner")}</span>
            ) : null}
          </label>
        ) : isEligibleAssignee && user ? (
          <p style={{ ...sharedStyles.meta, marginTop: "4px" }}>
            {t("assignedAutomatically")}
          </p>
        ) : null}

        {formError ? (
          <div style={sharedStyles.error} role="alert">
            {formError}
          </div>
        ) : null}

        <button style={styles.button} type="submit" disabled={isSubmitting || !user}>
          {isSubmitting ? messages("loading.saving") : t("actions.create")}
        </button>
      </form>
      ) : null}

      {isLoading ? <div style={sharedStyles.state}>{t("loading")}</div> : null}

      {!isLoading && error ? (
        <div style={sharedStyles.error} role="alert">
          {error}
        </div>
      ) : null}

      {!isLoading && !error && followUps.length === 0 ? (
        <div style={sharedStyles.state}>{t("empty")}</div>
      ) : null}

      {!isLoading && !error && followUps.length > 0 ? (
        <div style={sharedStyles.list}>
          {followUps.map((followUp) => (
            <article key={followUp.id} style={sharedStyles.item}>
              <div style={sharedStyles.itemHeader}>
                <div>
                  <h3 style={sharedStyles.itemTitle}>{followUp.reason}</h3>
                  <p style={sharedStyles.meta}>
                    {t("fields.dueDate")}: {fmt.dateTime(followUp.due_date)}
                    {" · "}
                    <FollowUpPriorityBadge priority={followUp.priority} />
                  </p>
                </div>
                <FollowUpStatusBadge status={followUp.status} isOverdue={followUp.is_overdue} />
              </div>

              <p style={sharedStyles.text}>
                {t("fields.assignedUser")}:{" "}
                {followUp.is_unassigned
                  ? t("unassigned")
                  : displayValue(followUp.assigned_user?.full_name ?? null)}
              </p>
              {followUp.is_unassigned &&
              (followUp.status === "pending" || followUp.status === "in_progress") ? (
                <div style={sharedStyles.modalWarning}>{t("needsReassignment")}</div>
              ) : null}
              <p style={sharedStyles.text}>
                {t("fields.notes")}: {displayValue(followUp.notes)}
              </p>
              {followUp.completed_at ? (
                <p style={sharedStyles.meta}>
                  {t("fields.completedAt")}: {fmt.dateTime(followUp.completed_at)}
                </p>
              ) : null}

              <div style={styles.actionsRow}>
                {canAssign &&
                followUp.is_unassigned &&
                (followUp.status === "pending" || followUp.status === "in_progress") ? (
                  <Link href="/follow-ups?unassigned=true" style={styles.compactButton}>
                    {t("actions.reassign")}
                  </Link>
                ) : null}
                {(followUp.status === "pending" || followUp.status === "in_progress") &&
                canComplete ? (
                  <button
                    style={styles.compactButton}
                    type="button"
                    disabled={actionId === followUp.id}
                    onClick={() =>
                      void runAction(followUp.id, () => completeFollowUp(followUp.id))
                    }
                  >
                    {actionId === followUp.id ? messages("loading.submitting") : t("actions.complete")}
                  </button>
                ) : null}

                {(followUp.status === "completed" || followUp.status === "cancelled") &&
                canUpdate ? (
                  <button
                    style={styles.compactButton}
                    type="button"
                    disabled={actionId === followUp.id}
                    onClick={() => void runAction(followUp.id, () => reopenFollowUp(followUp.id))}
                  >
                    {actionId === followUp.id ? messages("loading.submitting") : t("actions.reopen")}
                  </button>
                ) : null}

                {(followUp.status === "pending" || followUp.status === "in_progress") &&
                canUpdate ? (
                  <button
                    style={styles.compactButton}
                    type="button"
                    disabled={actionId === followUp.id}
                    onClick={() => void runAction(followUp.id, () => cancelFollowUp(followUp.id))}
                  >
                    {actionId === followUp.id ? messages("loading.submitting") : t("actions.cancel")}
                  </button>
                ) : null}

                {canDelete ? (
                  <button
                    style={styles.dangerButton}
                    type="button"
                    disabled={actionId === followUp.id}
                    onClick={() => void handleDelete(followUp.id)}
                  >
                    {actionId === followUp.id ? messages("loading.submitting") : t("actions.delete")}
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </SectionShell>
    </>
  );
}

function PriorityOptionLabel({ priority }: { priority: FollowUpFormValues["priority"] }) {
  const tEnums = useTranslations();
  return <>{tEnums(`enums.followUp.priority.${priority}`)}</>;
}
