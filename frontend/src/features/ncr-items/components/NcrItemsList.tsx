"use client";

import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { SectionShell } from "@/components/layout/section-shell";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { getItemsByReport } from "../api/ncr-items-api";
import type { NcrItemListItem } from "../types";
import { NcrItemForm } from "./NcrItemForm";

type NcrItemsListProps = {
  ncrReportId: string;
  reportStatus: string;
};

const styles: Record<string, CSSProperties> = {
  headerActions: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "12px",
  },
  itemMetaRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
    alignItems: "center",
  },
  lineBadge: {
    ...sharedStyles.badge,
    background: "var(--accent-soft)",
    color: "var(--accent-strong)",
    textTransform: "none",
  },
  reference: {
    ...sharedStyles.meta,
    background: "var(--surface-muted)",
    borderRadius: "999px",
    padding: "4px 8px",
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

export function NcrItemsList({ ncrReportId, reportStatus }: NcrItemsListProps) {
  const t = useTranslations("ncr.ncrReports.items");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [items, setItems] = useState<NcrItemListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [expandedItemIds, setExpandedItemIds] = useState<Set<string>>(new Set());
  const isMountedRef = useRef(true);
  const isClosed = reportStatus === "closed";

  const loadItems = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await getItemsByReport(ncrReportId);
      if (isMountedRef.current) {
        setItems(response);
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
  }, [ncrReportId, t]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadItems();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadItems]);

  function toggleDescription(itemId: string) {
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
      titleId="ncr-items-title"
      title={t("sectionTitle")}
      subtitle={t("sectionSubtitle")}
    >
      <div style={styles.headerActions}>
        <p style={{ ...sharedStyles.meta, margin: 0 }}>
          {t("lineNoAutoSentence")}
        </p>
        {!isClosed && !isFormOpen ? (
          <button
            style={sharedStyles.button}
            type="button"
            onClick={() => setIsFormOpen(true)}
          >
            {t("addButton")}
          </button>
        ) : null}
      </div>

      {isClosed ? (
        <div style={sharedStyles.state}>{t("statusGuardMessage")}</div>
      ) : null}

      {!isClosed && isFormOpen ? (
        <NcrItemForm
          ncrReportId={ncrReportId}
          onCreated={loadItems}
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
            onClick={() => void loadItems()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && items.length === 0 ? (
        <div style={sharedStyles.state}>{t("empty")}</div>
      ) : null}

      {!isLoading && !error && items.length > 0 ? (
        <div style={sharedStyles.list}>
          {items.map((item) => {
            const isExpanded = expandedItemIds.has(item.id);
            const isLongDescription = item.issue_description.length > 180;
            const description =
              isExpanded || !isLongDescription
                ? item.issue_description
                : `${item.issue_description.slice(0, 179)}...`;

            return (
              <article key={item.id} style={sharedStyles.item}>
                <div style={sharedStyles.itemHeader}>
                  <div>
                    <h3 style={sharedStyles.itemTitle}>{item.item_name}</h3>
                    <div style={styles.itemMetaRow}>
                      <span style={styles.lineBadge}>#{item.line_no}</span>
                      {item.item_reference ? (
                        <span style={styles.reference}>{item.item_reference}</span>
                      ) : null}
                      <span style={sharedStyles.meta}>
                        {fmt.quantity(item.quantity_affected, item.unit)}
                      </span>
                    </div>
                  </div>
                </div>

                <p style={styles.description}>
                  {description}
                  {isLongDescription ? (
                    <>
                      {" "}
                      <button
                        style={styles.inlineButton}
                        type="button"
                        onClick={() => toggleDescription(item.id)}
                      >
                        {isExpanded ? t("showLess") : t("showMore")}
                      </button>
                    </>
                  ) : null}
                </p>

                {item.notes ? (
                  <p style={sharedStyles.text}>
                    {t("notesLabel", { value: displayValue(item.notes) })}
                  </p>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : null}
    </SectionShell>
  );
}
