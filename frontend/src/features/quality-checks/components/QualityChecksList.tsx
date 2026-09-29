"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getQualityChecks } from "../api/quality-checks-api";
import type {
  QualityCheckListFilters,
  QualityCheckListItem,
  QualityCheckResult,
  QualityCheckStatus,
  QualityCheckType,
} from "../types";
import { QualityCheckResultBadge } from "./QualityCheckResultBadge";
import { QualityCheckStatusBadge } from "./QualityCheckStatusBadge";
import { formatCheckType, shortId } from "./quality-check-utils";

type FilterValues = {
  check_type: "" | QualityCheckType;
  status: "" | QualityCheckStatus;
  result: "" | QualityCheckResult;
  production_order_id: string;
  shift_report_id: string;
};

const defaultFilters: FilterValues = {
  check_type: "",
  status: "",
  result: "",
  production_order_id: "",
  shift_report_id: "",
};

const styles: Record<string, CSSProperties> = {
  filters: {
    display: "grid",
    gap: "14px",
    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
    marginBottom: "18px",
  },
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
};

export function QualityChecksList() {
  const t = useTranslations("quality.qualityChecks");
  const tEnums = useTranslations();
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [checks, setChecks] = useState<QualityCheckListItem[]>([]);
  const [filters, setFilters] = useState<FilterValues>(defaultFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadQualityChecks = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await getQualityChecks(toApiFilters(filters));

      if (isMountedRef.current) {
        setChecks(response);
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
    void loadQualityChecks();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadQualityChecks]);

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
      section="Quality"
      title={t("listTitle")}
      subtitle={t("subtitle")}
      action={
        <Link href="/quality-checks/new" style={sharedStyles.button}>
          {t("newButton")}
        </Link>
      }
    >
      <section style={styles.filters} aria-label={t("filtersAria")}>
        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.checkType")}</span>
          <select
            style={sharedStyles.input}
            value={filters.check_type}
            onChange={(event) =>
              updateFilter("check_type", event.target.value as FilterValues["check_type"])
            }
          >
            <option value="">All types</option>
            <option value="in_process_inspection">In-Process Inspection</option>
            <option value="finished_product_inspection">Finished Product Inspection</option>
            <option value="sample_inspection">Sample Inspection</option>
            <option value="reinspection">Re-inspection</option>
            <option value="issue_triggered">Issue Triggered</option>
            <option value="general">General</option>
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
            <option value="under_inspection">Under Inspection</option>
            <option value="closed">Closed</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.result")}</span>
          <select
            style={sharedStyles.input}
            value={filters.result}
            onChange={(event) =>
              updateFilter("result", event.target.value as FilterValues["result"])
            }
          >
            <option value="">All results</option>
            <option value="accepted">Accepted</option>
            <option value="rejected">Rejected</option>
            <option value="conditional_accept">Conditional Accept</option>
            <option value="needs_reinspection">Needs Reinspection</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.productionOrderId")}</span>
          <input
            style={sharedStyles.input}
            value={filters.production_order_id}
            onChange={(event) => updateFilter("production_order_id", event.target.value)}
          />
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.shiftReportId")}</span>
          <input
            style={sharedStyles.input}
            value={filters.shift_report_id}
            onChange={(event) => updateFilter("shift_report_id", event.target.value)}
          />
        </label>
      </section>

      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
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
            onClick={() => void loadQualityChecks()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && checks.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>
            {t("empty")}
          </h2>
          <p style={{ margin: "0 0 18px" }}>
            {t("createFirst")}
          </p>
          <Link href="/quality-checks/new" style={sharedStyles.button}>
            {t("createButton")}
          </Link>
        </section>
      ) : null}

      {!isLoading && !error && checks.length > 0 ? (
        <section style={styles.panel} aria-label={t("listAria")}>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t("fields.inspectionCode")}</th>
                  <th style={styles.th}>{t("fields.checkDate")}</th>
                  <th style={styles.th}>{t("fields.checkType")}</th>
                  <th style={styles.th}>{t("fields.status")}</th>
                  <th style={styles.th}>{t("fields.result")}</th>
                  <th style={styles.th}>{t("fields.qtyInspected")}</th>
                  <th style={styles.th}>{t("fields.productionOrder")}</th>
                </tr>
              </thead>
              <tbody>
                {checks.map((check) => (
                  <tr key={check.id}>
                    <td style={styles.td}>
                      <Link href={`/quality-checks/${check.id}`} style={styles.link}>
                        {check.inspection_code}
                      </Link>
                    </td>
                    <td style={styles.td}>{fmt.dateTime(check.check_datetime)}</td>
                    <td style={styles.td}>
                      <span style={checkTypeBadgeStyle}>
                        {formatCheckType(check.check_type, tEnums)}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <QualityCheckStatusBadge status={check.status} />
                    </td>
                    <td style={styles.td}>
                      <QualityCheckResultBadge result={check.result} />
                    </td>
                    <td style={styles.td}>{fmt.number(check.qty_inspected)}</td>
                    <td style={styles.td}>
                      {check.production_order_id ? (
                        <Link
                          href={`/production-orders/${check.production_order_id}`}
                          style={styles.link}
                        >
                          {shortId(check.production_order_id)}
                        </Link>
                      ) : (
                        "-"
                      )}
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

function toApiFilters(filters: FilterValues): QualityCheckListFilters {
  return {
    check_type: filters.check_type || undefined,
    status: filters.status || undefined,
    result: filters.result || undefined,
    production_order_id: filters.production_order_id.trim() || undefined,
    shift_report_id: filters.shift_report_id.trim() || undefined,
  };
}

const checkTypeBadgeStyle: CSSProperties = {
  ...sharedStyles.badge,
  background: "var(--accent-soft)",
  color: "var(--accent-strong)",
};
