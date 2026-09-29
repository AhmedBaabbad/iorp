"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { ActionFollowUpsList } from "@/features/action-follow-ups";
import { ClosureVerificationSection } from "@/features/closure-verifications";
import { useFormatter } from "@/hooks/useFormatter";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { correctiveActionTypeColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import {
  getCorrectiveActionById,
  updateCorrectiveActionStatus,
} from "../api/corrective-actions-api";
import type {
  CorrectiveActionDetail as CorrectiveActionData,
  CorrectiveActionSourceType,
  CorrectiveActionStatus,
  CorrectiveActionType,
} from "../types";
import { CorrectiveActionPriorityBadge } from "./CorrectiveActionPriorityBadge";
import { CorrectiveActionStatusBadge } from "./CorrectiveActionStatusBadge";

type CorrectiveActionDetailProps = {
  correctiveActionId: string;
};

const styles: Record<string, CSSProperties> = {
  detailGrid: {
    display: "grid",
    gap: "1px",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    background: "var(--border)",
    borderRadius: "8px",
    overflow: "hidden",
  },
  detailItem: {
    background: "var(--surface)",
    padding: "18px",
  },
  detailLabel: {
    color: "var(--text-muted)",
    fontSize: "13px",
    fontWeight: 700,
    margin: "0 0 8px",
  },
  detailValue: {
    margin: 0,
    overflowWrap: "anywhere",
  },
  section: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    marginTop: "18px",
    padding: "18px",
  },
  sectionTitle: {
    fontSize: "18px",
    margin: "0 0 12px",
  },
  actions: {
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
    marginBottom: "18px",
  },
  description: {
    background: "var(--surface-muted)",
    border: "1px solid var(--border)",
    borderRadius: "6px",
    lineHeight: 1.55,
    margin: 0,
    padding: "14px",
    whiteSpace: "pre-wrap",
  },
  link: {
    color: "var(--accent-strong)",
  },
};

export function CorrectiveActionDetail({
  correctiveActionId,
}: CorrectiveActionDetailProps) {
  const t = useTranslations("capa.correctiveActions");
  const tEnums = useTranslations();
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [action, setAction] = useState<CorrectiveActionData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let isMounted = true;

    async function loadCorrectiveAction() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const response = await getCorrectiveActionById(correctiveActionId);

        if (isMounted) {
          setAction(response);
        }
      } catch (caughtError) {
        if (!isMounted) {
          return;
        }

        if (caughtError instanceof ApiClientError && caughtError.status === 404) {
          setIsNotFound(true);
          return;
        }

        setError(getApiErrorMessage(caughtError, messages));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadCorrectiveAction();

    return () => {
      isMounted = false;
    };
  }, [correctiveActionId, reloadToken, t]);

  async function handleStatusAction(nextStatus: CorrectiveActionStatus) {
    setActionError(null);
    setIsUpdating(true);

    try {
      const updatedAction = await updateCorrectiveActionStatus(correctiveActionId, {
        status: nextStatus,
      });
      setAction(updatedAction);
    } catch (caughtError) {
      setActionError(
        getApiErrorMessage(caughtError, messages),
      );
    } finally {
      setIsUpdating(false);
    }
  }

  return (
    <PageFrame
      section="CAPA"
      title={action?.action_code ?? t("detailTitle")}
      subtitle={action ? action.title : t("detailSubtitle")}
      action={
        <Link href="/corrective-actions" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          {t("loadingDetail")}
        </div>
      ) : null}

      {!isLoading && isNotFound ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>
            {t("notFound")}
          </h2>
          <p style={{ margin: "0 0 18px" }}>
            {t("notFoundDescription")}
          </p>
          <Link href="/corrective-actions" style={sharedStyles.button}>
            {t("backToList")}
          </Link>
        </section>
      ) : null}

      {!isLoading && error ? (
        <div style={{ display: "grid", gap: "12px" }}>
          <div style={sharedStyles.error} role="alert">
            {error}
          </div>
          <button
            style={{ ...sharedStyles.secondaryButton, width: "fit-content" }}
            type="button"
            onClick={() => setReloadToken((current) => current + 1)}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && !isNotFound && action ? (
        <>
          <div style={styles.actions}>
            {action.status === "open" ? (
              <button
                style={sharedStyles.button}
                type="button"
                disabled={isUpdating}
                onClick={() => void handleStatusAction("in_progress")}
              >
                {isUpdating ? t("statusActions.starting") : t("statusActions.start")}
              </button>
            ) : null}

            {action.status === "in_progress" ? (
              <button
                style={sharedStyles.button}
                type="button"
                disabled={isUpdating}
                onClick={() => void handleStatusAction("completed")}
              >
                {isUpdating ? t("statusActions.completing") : t("statusActions.complete")}
              </button>
            ) : null}

            {action.status === "completed" ? (
              <>
                <button
                  style={sharedStyles.button}
                  type="button"
                  disabled={isUpdating}
                  onClick={() => void handleStatusAction("closed")}
                >
                  {isUpdating ? t("statusActions.closing") : t("statusActions.close")}
                </button>
                <div style={sharedStyles.state}>
                  {t("verificationBeforeClose")}
                </div>
              </>
            ) : null}

            {action.status === "closed" ? (
              <div style={sharedStyles.state}>{t("closedMessage")}</div>
            ) : null}
          </div>

          {actionError ? (
            <div style={{ ...sharedStyles.error, marginBottom: "18px" }} role="alert">
              {actionError}
            </div>
          ) : null}

          <section style={styles.detailGrid} aria-label={t("detailTitle")}>
            <DetailItem label={t("fields.actionCode")} value={action.action_code} />
            <DetailItem label={t("fields.title")} value={action.title} />
            <DetailItem
              label={t("fields.actionType")}
              value={
                <span style={actionTypeBadgeStyle(action.action_type)}>
                  {formatActionType(action.action_type, tEnums)}
                </span>
              }
            />
            <DetailItem
              label={t("fields.priority")}
              value={<CorrectiveActionPriorityBadge priority={action.priority} />}
            />
            <DetailItem
              label={t("fields.status")}
              value={<CorrectiveActionStatusBadge status={action.status} />}
            />
            <DetailItem label={t("fields.dueDate")} value={fmt.date(action.due_date)} />
            <DetailItem label={t("fields.owner")} value={action.owner_user_id} />
          </section>

          <section style={styles.section} aria-label={t("descriptionSection")}>
            <h2 style={styles.sectionTitle}>{t("descriptionSection")}</h2>
            <p style={styles.description}>{action.description}</p>
          </section>

          <section style={styles.section} aria-label={t("sourceSection")}>
            <h2 style={styles.sectionTitle}>{t("sourceSection")}</h2>
            <section style={styles.detailGrid}>
              <DetailItem
                label={t("fields.sourceType")}
                value={
                  action.source_type
                    ? formatSourceType(action.source_type, tEnums)
                    : t("noSourceSelected")
                }
              />
              <DetailItem label={t("fields.sourceId")} value={renderSourceLink(action, t, tEnums)} />
            </section>
          </section>

          {action.notes ? (
            <section style={styles.section} aria-label={t("fields.notes")}>
              <h2 style={styles.sectionTitle}>{t("fields.notes")}</h2>
              <p style={styles.description}>{action.notes}</p>
            </section>
          ) : null}

          <ActionFollowUpsList
            correctiveActionId={action.id}
            correctiveActionStatus={action.status}
          />

          <ClosureVerificationSection
            correctiveActionId={action.id}
            correctiveActionStatus={action.status}
          />
        </>
      ) : null}
    </PageFrame>
  );
}

function DetailItem({
  label,
  value,
}: {
  label: string;
  value: string | number | null | ReactNode;
}) {
  return (
    <div style={styles.detailItem}>
      <p style={styles.detailLabel}>{label}</p>
      <p style={styles.detailValue}>
        {typeof value === "string" || typeof value === "number" || value === null
          ? displayValue(value)
          : value}
      </p>
    </div>
  );
}

function renderSourceLink(
  action: CorrectiveActionData,
  t: (key: string) => string,
  tEnums: (key: string) => string,
) {
  if (action.source_type === "manual") {
    return t("manualSource");
  }

  if (!action.source_type || !action.source_id) {
    return null;
  }

  const href = sourceHref(action.source_type, action.source_id);
  if (!href) {
    return `${formatSourceType(action.source_type, tEnums)}: ${shortId(action.source_id)}`;
  }

  return (
    <Link href={href} style={styles.link}>
      {formatSourceType(action.source_type, tEnums)}: {shortId(action.source_id)}
    </Link>
  );
}

function sourceHref(sourceType: CorrectiveActionSourceType, sourceId: string) {
  const hrefs: Partial<Record<CorrectiveActionSourceType, string>> = {
    quality_rejection: `/quality-rejections/${sourceId}`,
    ncr_report: `/non-conformance-reports/${sourceId}`,
  };

  return hrefs[sourceType] ?? null;
}

function formatActionType(value: CorrectiveActionType, t: (key: string) => string) {
  return getEnumLabel("correctiveAction", "actionType", value, t);
}

function formatSourceType(value: CorrectiveActionSourceType, t: (key: string) => string) {
  return getEnumLabel("correctiveAction", "sourceType", value, t);
}

function shortId(value: string) {
  return value.length > 8 ? value.slice(0, 8) : value;
}

function actionTypeBadgeStyle(value: CorrectiveActionType): CSSProperties {
  return { ...sharedStyles.badge, ...correctiveActionTypeColors[value] };
}
