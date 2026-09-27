"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { useFormatter } from "@/hooks/useFormatter";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { correctiveActionTypeColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import { getCorrectiveActions } from "../api/corrective-actions-api";
import type {
  CorrectiveActionListFilters,
  CorrectiveActionListItem,
  CorrectiveActionPriority,
  CorrectiveActionSourceType,
  CorrectiveActionStatus,
  CorrectiveActionType,
} from "../types";
import { CorrectiveActionPriorityBadge } from "./CorrectiveActionPriorityBadge";
import { CorrectiveActionStatusBadge } from "./CorrectiveActionStatusBadge";

type FilterValues = {
  action_type: "" | CorrectiveActionType;
  status: "" | CorrectiveActionStatus;
  priority: "" | CorrectiveActionPriority;
  source_type: "" | CorrectiveActionSourceType;
};

const defaultFilters: FilterValues = {
  action_type: "",
  status: "",
  priority: "",
  source_type: "",
};

const styles: Record<string, CSSProperties> = {
  filters: {
    display: "grid",
    gap: "14px",
    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
    marginBottom: "18px",
  },
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
    textAlign: "left",
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
};

export function CorrectiveActionsList() {
  const t = useTranslations("capa.correctiveActions");
  const tEnums = useTranslations();
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [actions, setActions] = useState<CorrectiveActionListItem[]>([]);
  const [filters, setFilters] = useState<FilterValues>(defaultFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadCorrectiveActions = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await getCorrectiveActions(toApiFilters(filters));
      if (isMountedRef.current) {
        setActions(response);
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
  }, [filters, t]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadCorrectiveActions();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadCorrectiveActions]);

  function updateFilter<TField extends keyof FilterValues>(
    field: TField,
    value: FilterValues[TField],
  ) {
    setFilters((current) => ({
      ...current,
      [field]: value,
    }));
  }

  return (
    <PageFrame
      section="CAPA"
      title={t("listTitle")}
      subtitle={t("subtitle")}
      action={
        <Link href="/corrective-actions/new" style={sharedStyles.button}>
          {t("newButton")}
        </Link>
      }
    >
      <section style={styles.filters} aria-label={t("filtersAria")}>
        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.actionType")}</span>
          <select
            style={sharedStyles.input}
            value={filters.action_type}
            onChange={(event) =>
              updateFilter("action_type", event.target.value as FilterValues["action_type"])
            }
          >
            <option value="">All types</option>
            <option value="corrective">Corrective</option>
            <option value="preventive">Preventive</option>
            <option value="improvement">Improvement</option>
            <option value="containment">Containment</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.status")}</span>
          <select
            style={sharedStyles.input}
            value={filters.status}
            onChange={(event) =>
              updateFilter("status", event.target.value as FilterValues["status"])
            }
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="closed">Closed</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.priority")}</span>
          <select
            style={sharedStyles.input}
            value={filters.priority}
            onChange={(event) =>
              updateFilter("priority", event.target.value as FilterValues["priority"])
            }
          >
            <option value="">All priorities</option>
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="normal">Normal</option>
            <option value="low">Low</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.sourceType")}</span>
          <select
            style={sharedStyles.input}
            value={filters.source_type}
            onChange={(event) =>
              updateFilter("source_type", event.target.value as FilterValues["source_type"])
            }
          >
            <option value="">All sources</option>
            <option value="quality_rejection">Quality Rejection</option>
            <option value="ncr_report">NCR Report</option>
            <option value="quality_defect">Quality Defect</option>
            <option value="ncr_item">NCR Item</option>
            <option value="manual">Manual</option>
          </select>
        </label>
      </section>

      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "#ffffff" }}>
          {t("loading")}
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
            onClick={() => void loadCorrectiveActions()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && actions.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "#ffffff" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>
            {t("empty")}
          </h2>
          <p style={{ margin: "0 0 18px" }}>
            {t("createFirst")}
          </p>
          <Link href="/corrective-actions/new" style={sharedStyles.button}>
            {t("newButton")}
          </Link>
        </section>
      ) : null}

      {!isLoading && !error && actions.length > 0 ? (
        <section style={styles.panel} aria-label={t("listAria")}>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t("fields.actionCode")}</th>
                  <th style={styles.th}>{t("fields.title")}</th>
                  <th style={styles.th}>{t("fields.actionType")}</th>
                  <th style={styles.th}>{t("fields.priority")}</th>
                  <th style={styles.th}>{t("fields.status")}</th>
                  <th style={styles.th}>{t("fields.dueDate")}</th>
                  <th style={styles.th}>{t("fields.owner")}</th>
                </tr>
              </thead>
              <tbody>
                {actions.map((action) => (
                  <tr key={action.id}>
                    <td style={styles.td}>
                      <Link href={`/corrective-actions/${action.id}`} style={styles.link}>
                        {action.action_code}
                      </Link>
                    </td>
                    <td style={styles.td}>{truncateText(action.title, 72)}</td>
                    <td style={styles.td}>
                      <span style={actionTypeBadgeStyle(action.action_type)}>
                        {formatActionType(action.action_type, tEnums)}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <CorrectiveActionPriorityBadge priority={action.priority} />
                    </td>
                    <td style={styles.td}>
                      <CorrectiveActionStatusBadge status={action.status} />
                    </td>
                    <td style={styles.td}>{fmt.date(action.due_date)}</td>
                    <td style={styles.td}>{action.owner_user_id}</td>
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

function toApiFilters(filters: FilterValues): CorrectiveActionListFilters {
  return {
    action_type: filters.action_type || undefined,
    status: filters.status || undefined,
    priority: filters.priority || undefined,
    source_type: filters.source_type || undefined,
  };
}

function truncateText(value: string, maxLength: number) {
  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, maxLength - 1)}...`;
}

function formatActionType(value: CorrectiveActionType, t: (key: string) => string) {
  return getEnumLabel("correctiveAction", "actionType", value, t);
}

function actionTypeBadgeStyle(value: CorrectiveActionType): CSSProperties {
  return { ...sharedStyles.badge, ...correctiveActionTypeColors[value] };
}
