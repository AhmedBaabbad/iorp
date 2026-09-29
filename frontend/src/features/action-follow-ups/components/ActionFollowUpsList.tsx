"use client";

import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { SectionShell } from "@/components/layout/section-shell";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { getFollowUpsByAction } from "../api/action-follow-ups-api";
import type { ActionFollowUpListItem } from "../types";
import { ActionFollowUpForm } from "./ActionFollowUpForm";
import { FollowUpStatusBadge } from "./FollowUpStatusBadge";

type ActionFollowUpsListProps = {
  correctiveActionId: string;
  correctiveActionStatus: string;
};

const styles: Record<string, CSSProperties> = {
  headerActions: {
    display: "flex",
    justifyContent: "flex-end",
  },
  itemMetaRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
    alignItems: "center",
  },
  description: {
    ...sharedStyles.text,
    whiteSpace: "pre-wrap",
  },
  inlineButton: {
    background: "transparent",
    border: 0,
    color: "var(--accent-strong)",
    cursor: "pointer",
    font: "inherit",
    padding: 0,
  },
};

export function ActionFollowUpsList({
  correctiveActionId,
  correctiveActionStatus,
}: ActionFollowUpsListProps) {
  const t = useTranslations("capa.correctiveActions.followUps");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [followUps, setFollowUps] = useState<ActionFollowUpListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [expandedItemIds, setExpandedItemIds] = useState<Set<string>>(new Set());
  const isMountedRef = useRef(true);
  const isClosed = correctiveActionStatus === "closed";

  const loadFollowUps = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await getFollowUpsByAction(correctiveActionId);
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
  }, [correctiveActionId, t]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadFollowUps();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadFollowUps]);

  async function handleFollowUpCreated() {
    await loadFollowUps();
    setIsFormOpen(false);
  }

  function toggleProgressNote(itemId: string) {
    setExpandedItemIds((current) => {
      const next = new Set(current);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  }

  return (
    <SectionShell
      titleId="action-follow-ups-title"
      title={t("sectionTitle")}
      subtitle={t("sectionSubtitle")}
    >
      {!isClosed && !isFormOpen ? (
        <div style={styles.headerActions}>
          <button
            style={sharedStyles.button}
            type="button"
            onClick={() => setIsFormOpen(true)}
          >
            {t("addButton")}
          </button>
        </div>
      ) : null}

      {isClosed ? (
        <div style={sharedStyles.state}>
          {t("statusGuardMessage")}
        </div>
      ) : null}

      {!isClosed && isFormOpen ? (
        <ActionFollowUpForm
          correctiveActionId={correctiveActionId}
          onCreated={handleFollowUpCreated}
          onCancel={() => setIsFormOpen(false)}
        />
      ) : null}

      {isLoading ? <div style={sharedStyles.state}>{t("loading")}</div> : null}

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

      {!isLoading && !error && followUps.length === 0 ? (
        <div style={sharedStyles.state}>{t("empty")}</div>
      ) : null}

      {!isLoading && !error && followUps.length > 0 ? (
        <div style={sharedStyles.list}>
          {followUps.map((followUp) => {
            const isExpanded = expandedItemIds.has(followUp.id);
            const isLongProgressNote = followUp.progress_note.length > 180;
            const progressNote =
              isExpanded || !isLongProgressNote
                ? followUp.progress_note
                : `${followUp.progress_note.slice(0, 179)}...`;

            return (
              <article key={followUp.id} style={sharedStyles.item}>
                <div style={sharedStyles.itemHeader}>
                  <div>
                    <h3 style={sharedStyles.itemTitle}>
                      {fmt.date(followUp.follow_up_date)}
                    </h3>
                    <div style={styles.itemMetaRow}>
                      <FollowUpStatusBadge status={followUp.status} />
                      {followUp.created_by_user_id ? (
                        <span style={sharedStyles.meta}>
                          {t("createdBy", { userId: followUp.created_by_user_id })}
                        </span>
                      ) : null}
                    </div>
                  </div>
                </div>

                <p style={styles.description}>
                  {progressNote}
                  {isLongProgressNote ? (
                    <>
                      {" "}
                      <button
                        style={styles.inlineButton}
                        type="button"
                        onClick={() => toggleProgressNote(followUp.id)}
                      >
                        {isExpanded ? t("showLess") : t("showMore")}
                      </button>
                    </>
                  ) : null}
                </p>

                <p style={sharedStyles.text}>
                  {t("nextStepLabel", { value: displayValue(followUp.next_step) })}
                </p>
              </article>
            );
          })}
        </div>
      ) : null}
    </SectionShell>
  );
}
