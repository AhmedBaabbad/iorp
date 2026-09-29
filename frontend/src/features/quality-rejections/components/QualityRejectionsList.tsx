"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getQualityRejections } from "../api/quality-rejections-api";
import type {
  Disposition,
  DispositionStatus,
  QualityRejectionListFilters,
  QualityRejectionListItem,
  RejectionReason,
} from "../types";
import { DispositionBadge } from "./DispositionBadge";
import { DispositionStatusBadge } from "./DispositionStatusBadge";
import { formatRejectionReason, shortId } from "./quality-rejection-utils";

type FilterValues = {
  rejection_reason: "" | RejectionReason;
  disposition: "" | Disposition;
  disposition_status: "" | DispositionStatus;
  quality_check_id: string;
  rejection_date: string;
};

const defaultFilters: FilterValues = {
  rejection_reason: "",
  disposition: "",
  disposition_status: "",
  quality_check_id: "",
  rejection_date: "",
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

export function QualityRejectionsList() {
  const t = useTranslations("quality.qualityRejections");
  const tEnums = useTranslations();
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [rejections, setRejections] = useState<QualityRejectionListItem[]>([]);
  const [filters, setFilters] = useState<FilterValues>(defaultFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadRejections = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await getQualityRejections(toApiFilters(filters));

      if (isMountedRef.current) {
        setRejections(response);
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
    void loadRejections();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadRejections]);

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
        <Link href="/quality-rejections/new" style={sharedStyles.button}>
          {t("newButton")}
        </Link>
      }
    >
      <section style={styles.filters} aria-label={t("filtersAria")}>
        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.rejectionReason")}</span>
          <select
            style={sharedStyles.input}
            value={filters.rejection_reason}
            onChange={(event) =>
              updateFilter("rejection_reason", event.target.value as FilterValues["rejection_reason"])
            }
          >
            <option value="">All reasons</option>
            <option value="failed_quality_check">Failed Quality Check</option>
            <option value="critical_defect">Critical Defect</option>
            <option value="out_of_spec">Out of Specification</option>
            <option value="dimension_failure">Dimension Failure</option>
            <option value="surface_failure">Surface Failure</option>
            <option value="packaging_failure">Packaging Failure</option>
            <option value="labeling_issue">Labeling Issue</option>
            <option value="other">Other</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.disposition")}</span>
          <select
            style={sharedStyles.input}
            value={filters.disposition}
            onChange={(event) =>
              updateFilter("disposition", event.target.value as FilterValues["disposition"])
            }
          >
            <option value="">All dispositions</option>
            <option value="hold">Hold</option>
            <option value="scrap">Scrap</option>
            <option value="rework">Rework</option>
            <option value="return_to_process">Return to Process</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.dispositionStatus")}</span>
          <select
            style={sharedStyles.input}
            value={filters.disposition_status}
            onChange={(event) =>
              updateFilter(
                "disposition_status",
                event.target.value as FilterValues["disposition_status"],
              )
            }
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="executed">Executed</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.qualityCheckId")}</span>
          <input
            style={sharedStyles.input}
            value={filters.quality_check_id}
            onChange={(event) => updateFilter("quality_check_id", event.target.value)}
          />
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.rejectionDate")}</span>
          <input
            style={sharedStyles.input}
            type="date"
            value={filters.rejection_date}
            onChange={(event) => updateFilter("rejection_date", event.target.value)}
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
            onClick={() => void loadRejections()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && rejections.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>
            {t("empty")}
          </h2>
          <p style={{ margin: "0 0 18px" }}>
            {t("createFirst")}
          </p>
          <Link href="/quality-rejections/new" style={sharedStyles.button}>
            {t("createButton")}
          </Link>
        </section>
      ) : null}

      {!isLoading && !error && rejections.length > 0 ? (
        <section style={styles.panel} aria-label={t("listAria")}>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t("fields.rejectionDate")}</th>
                  <th style={styles.th}>{t("fields.rejectionReason")}</th>
                  <th style={styles.th}>{t("fields.disposition")}</th>
                  <th style={styles.th}>{t("fields.execution")}</th>
                  <th style={styles.th}>{t("fields.quantityRejected")}</th>
                  <th style={styles.th}>{t("fields.qualityCheck")}</th>
                </tr>
              </thead>
              <tbody>
                {rejections.map((rejection) => (
                  <tr key={rejection.id}>
                    <td style={styles.td}>
                      <Link href={`/quality-rejections/${rejection.id}`} style={styles.link}>
                        {fmt.date(rejection.rejection_date)}
                      </Link>
                    </td>
                    <td style={styles.td}>{formatRejectionReason(rejection.rejection_reason, tEnums)}</td>
                    <td style={styles.td}>
                      <DispositionBadge disposition={rejection.disposition} />
                    </td>
                    <td style={styles.td}>
                      <DispositionStatusBadge status={rejection.disposition_status} />
                    </td>
                    <td style={styles.td}>
                      {fmt.quantity(rejection.quantity_rejected, rejection.unit)}
                    </td>
                    <td style={styles.td}>
                      {rejection.quality_check_id ? (
                        <Link
                          href={`/quality-checks/${rejection.quality_check_id}`}
                          style={styles.link}
                        >
                          {shortId(rejection.quality_check_id)}
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

function toApiFilters(filters: FilterValues): QualityRejectionListFilters {
  return {
    rejection_reason: filters.rejection_reason || undefined,
    disposition: filters.disposition || undefined,
    disposition_status: filters.disposition_status || undefined,
    quality_check_id: filters.quality_check_id.trim() || undefined,
    rejection_date: filters.rejection_date || undefined,
  };
}
