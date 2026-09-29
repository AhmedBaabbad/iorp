"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getNCRReports } from "../api/ncr-reports-api";
import type {
  NCRReportType,
  NCRSourceType,
  NCRStatus,
  NcrReportListFilters,
  NcrReportListItem,
} from "../types";
import { NcrSourceTypeBadge } from "./NcrSourceTypeBadge";
import { NcrStatusBadge } from "./NcrStatusBadge";
import { formatReportType, truncateText } from "./ncr-report-utils";

type FilterValues = {
  source_type: "" | NCRSourceType;
  report_type: "" | NCRReportType;
  status: "" | NCRStatus;
  report_date: string;
};

const defaultFilters: FilterValues = {
  source_type: "",
  report_type: "",
  status: "",
  report_date: "",
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

export function NcrReportsList() {
  const t = useTranslations("ncr.ncrReports");
  const tEnums = useTranslations();
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [reports, setReports] = useState<NcrReportListItem[]>([]);
  const [filters, setFilters] = useState<FilterValues>(defaultFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadReports = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await getNCRReports(toApiFilters(filters));

      if (isMountedRef.current) {
        setReports(response);
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
    void loadReports();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadReports]);

  function updateFilter<TField extends keyof FilterValues>(
    field: TField,
    value: FilterValues[TField],
  ) {
    setFilters((current) => ({ ...current, [field]: value }));
  }

  return (
    <PageFrame
      section="Quality"
      title={t("listTitle")}
      subtitle={t("subtitle")}
      action={
        <Link href="/non-conformance-reports/new" style={sharedStyles.button}>
          {t("newButton")}
        </Link>
      }
    >
      <section style={styles.filters} aria-label={t("filtersAria")}>
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
            <option value="internal_production">Internal Production</option>
            <option value="incoming_material">Incoming Material</option>
            <option value="supplier">Supplier</option>
            <option value="warehouse">Warehouse</option>
            <option value="customer_return">Customer Return</option>
            <option value="other">Other</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.reportType")}</span>
          <select
            style={sharedStyles.input}
            value={filters.report_type}
            onChange={(event) =>
              updateFilter("report_type", event.target.value as FilterValues["report_type"])
            }
          >
            <option value="">All report types</option>
            <option value="material_non_conformance">Material Non-Conformance</option>
            <option value="product_non_conformance">Product Non-Conformance</option>
            <option value="process_non_conformance">Process Non-Conformance</option>
            <option value="packaging_non_conformance">Packaging Non-Conformance</option>
            <option value="documentation_non_conformance">Documentation Non-Conformance</option>
            <option value="other">Other</option>
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
            <option value="draft">Draft</option>
            <option value="open">Open</option>
            <option value="under_review">Under Review</option>
            <option value="closed">Closed</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.reportDate")}</span>
          <input
            style={sharedStyles.input}
            type="date"
            value={filters.report_date}
            onChange={(event) => updateFilter("report_date", event.target.value)}
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
            onClick={() => void loadReports()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && reports.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("empty")}</h2>
          <p style={{ margin: "0 0 18px" }}>
            {t("createFirst")}
          </p>
          <Link href="/non-conformance-reports/new" style={sharedStyles.button}>
            {t("createButton")}
          </Link>
        </section>
      ) : null}

      {!isLoading && !error && reports.length > 0 ? (
        <section style={styles.panel} aria-label={t("listAria")}>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t("fields.reportNumber")}</th>
                  <th style={styles.th}>{t("fields.reportDate")}</th>
                  <th style={styles.th}>{t("fields.sourceType")}</th>
                  <th style={styles.th}>{t("fields.reportType")}</th>
                  <th style={styles.th}>{t("fields.status")}</th>
                  <th style={styles.th}>{t("fields.title")}</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((report) => (
                  <tr key={report.id}>
                    <td style={styles.td}>
                      <Link href={`/non-conformance-reports/${report.id}`} style={styles.link}>
                        {report.report_number}
                      </Link>
                    </td>
                    <td style={styles.td}>{fmt.date(report.report_date)}</td>
                    <td style={styles.td}>
                      <NcrSourceTypeBadge sourceType={report.source_type} />
                    </td>
                    <td style={styles.td}>{formatReportType(report.report_type, tEnums)}</td>
                    <td style={styles.td}>
                      <NcrStatusBadge status={report.status} />
                    </td>
                    <td style={styles.td}>{truncateText(report.title, 60)}</td>
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

function toApiFilters(filters: FilterValues): NcrReportListFilters {
  return {
    source_type: filters.source_type || undefined,
    report_type: filters.report_type || undefined,
    status: filters.status || undefined,
    report_date: filters.report_date || undefined,
  };
}
