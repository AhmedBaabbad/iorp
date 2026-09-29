"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getShifts } from "@/features/shifts";
import { getWorkCenters } from "@/features/work-centers";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getShiftReports } from "../api/shift-reports-api";
import type {
  ShiftReportListFilters,
  ShiftReportListItem,
  ShiftReportStatus,
} from "../types";
import { ShiftReportStatusBadge } from "./ShiftReportStatusBadge";

type WorkCenterOption = {
  id: string;
  code: string;
  name: string;
};

type ShiftOption = {
  id: string;
  code: string;
  name: string;
  shift_type: string;
};

type FilterValues = {
  status: "" | ShiftReportStatus;
  work_center_id: string;
  shift_definition_id: string;
  report_date: string;
};

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
  },
  filters: {
    display: "grid",
    gap: "14px",
    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
    marginBottom: "18px",
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

const defaultFilters: FilterValues = {
  status: "",
  work_center_id: "",
  shift_definition_id: "",
  report_date: "",
};

export function ShiftReportsList() {
  const t = useTranslations("production.shiftReports");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [reports, setReports] = useState<ShiftReportListItem[]>([]);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [shifts, setShifts] = useState<ShiftOption[]>([]);
  const [filters, setFilters] = useState<FilterValues>(defaultFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadShiftReports = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const [reportsResponse, workCentersResponse, shiftsResponse] = await Promise.all([
        getShiftReports(toApiFilters(filters)),
        getWorkCenters().catch(() => []),
        getShifts().catch(() => []),
      ]);

      if (isMountedRef.current) {
        setReports(reportsResponse);
        setWorkCenters(workCentersResponse);
        setShifts(shiftsResponse);
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
    void loadShiftReports();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadShiftReports]);

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
      section="Production"
      title={t("listTitle")}
      subtitle={t("subtitle")}
      action={
        <Link href="/shift-reports/new" style={sharedStyles.button}>
          {t("newButton")}
        </Link>
      }
    >
      <section style={styles.filters} aria-label={t("filtersAria")}>
        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.status")}</span>
          <select
            style={sharedStyles.input}
            value={filters.status}
            onChange={(event) =>
              updateFilter("status", event.target.value as FilterValues["status"])
            }
          >
            <option value="">{t("allStatuses")}</option>
            <option value="draft">Draft</option>
            <option value="submitted">Submitted</option>
            <option value="approved">Approved</option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.workCenter")}</span>
          <select
            style={sharedStyles.input}
            value={filters.work_center_id}
            onChange={(event) => updateFilter("work_center_id", event.target.value)}
          >
            <option value="">{t("allWorkCenters")}</option>
            {workCenters.map((workCenter) => (
              <option key={workCenter.id} value={workCenter.id}>
                {workCenter.code} - {workCenter.name}
              </option>
            ))}
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.shift")}</span>
          <select
            style={sharedStyles.input}
            value={filters.shift_definition_id}
            onChange={(event) => updateFilter("shift_definition_id", event.target.value)}
          >
            <option value="">{t("allShifts")}</option>
            {shifts.map((shift) => (
              <option key={shift.id} value={shift.id}>
                {shift.code} - {shift.name}
              </option>
            ))}
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
            onClick={() => void loadShiftReports()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && reports.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>
            {t("empty")}
          </h2>
          <p style={{ margin: "0 0 18px" }}>
            {t("createFirst")}
          </p>
          <Link href="/shift-reports/new" style={sharedStyles.button}>
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
                  <th style={styles.th}>{t("fields.reportDate")}</th>
                  <th style={styles.th}>{t("fields.status")}</th>
                  <th style={styles.th}>{t("fields.summary")}</th>
                  <th style={styles.th}>{t("fields.workCenter")}</th>
                  <th style={styles.th}>{t("fields.shift")}</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((report) => (
                  <tr key={report.id}>
                    <td style={styles.td}>
                      <Link href={`/shift-reports/${report.id}`} style={styles.link}>
                        {fmt.date(report.report_date)}
                      </Link>
                    </td>
                    <td style={styles.td}>
                      <ShiftReportStatusBadge status={report.status} />
                    </td>
                    <td style={styles.td}>{truncateText(report.summary, 60)}</td>
                    <td style={styles.td}>
                      {formatWorkCenterLabel(workCenters, report.work_center_id)}
                    </td>
                    <td style={styles.td}>
                      {formatShiftLabel(shifts, report.shift_definition_id)}
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

function toApiFilters(filters: FilterValues): ShiftReportListFilters {
  return {
    status: filters.status || undefined,
    work_center_id: filters.work_center_id || undefined,
    shift_definition_id: filters.shift_definition_id || undefined,
    report_date: filters.report_date || undefined,
  };
}

function formatWorkCenterLabel(workCenters: WorkCenterOption[], workCenterId: string) {
  const workCenter = workCenters.find((item) => item.id === workCenterId);
  return workCenter ? `${workCenter.code} - ${workCenter.name}` : workCenterId;
}

function formatShiftLabel(shifts: ShiftOption[], shiftDefinitionId: string) {
  const shift = shifts.find((item) => item.id === shiftDefinitionId);
  return shift ? `${shift.code} - ${shift.name}` : shiftDefinitionId;
}

function truncateText(value: string, maxLength: number) {
  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, maxLength - 1)}...`;
}
