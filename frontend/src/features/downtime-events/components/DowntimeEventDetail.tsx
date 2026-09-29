"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties, FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getProductionOrders } from "@/features/production-orders";
import { getShiftReportById } from "@/features/shift-reports";
import { getWorkCenters } from "@/features/work-centers";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import {
  endDowntimeEvent,
  getDowntimeEventById,
} from "../api/downtime-events-api";
import type { DowntimeEventData } from "../types";
import { DowntimeCategoryBadge } from "./DowntimeCategoryBadge";
import { DowntimeStatusBadge } from "./DowntimeStatusBadge";
import {
  formatProductionOrderLabel,
  formatWorkCenterLabel,
  toIsoDatetime,
  type ProductionOrderOption,
  type WorkCenterOption,
} from "./downtime-events-utils";

type DowntimeEventDetailProps = {
  downtimeEventId: string;
};

type ShiftReportReference = {
  id: string;
  report_date: string;
};

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
    padding: "24px",
  },
  grid: {
    display: "grid",
    gap: "18px",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  },
  label: {
    color: "var(--text-muted)",
    display: "block",
    fontSize: "13px",
    marginBottom: "6px",
  },
  value: {
    color: "var(--text)",
    fontWeight: 700,
    margin: 0,
  },
  section: {
    borderTop: "1px solid var(--border)",
    display: "grid",
    gap: "12px",
    marginTop: "24px",
    paddingTop: "20px",
  },
  openAction: {
    background: "var(--warning-soft)",
    border: "1px solid color-mix(in srgb, var(--warning) 35%, var(--surface))",
    borderRadius: "8px",
    display: "grid",
    gap: "14px",
    marginTop: "24px",
    padding: "18px",
  },
  actionRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
    alignItems: "end",
  },
  link: {
    color: "var(--accent-strong)",
    fontWeight: 700,
    textDecoration: "none",
  },
};

export function DowntimeEventDetail({ downtimeEventId }: DowntimeEventDetailProps) {
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [event, setEvent] = useState<DowntimeEventData | null>(null);
  const [shiftReport, setShiftReport] = useState<ShiftReportReference | null>(null);
  const [workCenters, setWorkCenters] = useState<WorkCenterOption[]>([]);
  const [productionOrders, setProductionOrders] = useState<ProductionOrderOption[]>([]);
  const [endTime, setEndTime] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isEnding, setIsEnding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [endError, setEndError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadDowntimeEvent = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await getDowntimeEventById(downtimeEventId);
      if (response.shift_report_id) {
        getShiftReportById(response.shift_report_id)
          .then((report) => {
            if (isMountedRef.current) {
              setShiftReport(report);
            }
          })
          .catch(() => undefined);
      } else if (isMountedRef.current) {
        setShiftReport(null);
      }

      const [workCentersResponse, productionOrdersResponse] = await Promise.all([
        getWorkCenters().catch(() => []),
        getProductionOrders().catch(() => []),
      ]);

      if (isMountedRef.current) {
        setEvent(response);
        setWorkCenters(workCentersResponse);
        setProductionOrders(productionOrdersResponse);
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
  }, [downtimeEventId]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadDowntimeEvent();

    return () => {
      isMountedRef.current = false;
    };
  }, [loadDowntimeEvent]);

  async function handleEndDowntime(submitEvent: FormEvent<HTMLFormElement>) {
    submitEvent.preventDefault();
    setEndError(null);

    if (!endTime) {
      setEndError("End time is required to close downtime.");
      return;
    }

    setIsEnding(true);

    try {
      const closedEvent = await endDowntimeEvent(downtimeEventId, toIsoDatetime(endTime));
      if (isMountedRef.current) {
        setEvent(closedEvent);
        setEndTime("");
      }
    } catch (caughtError) {
      if (isMountedRef.current) {
      setEndError(getApiErrorMessage(caughtError, messages));
      }
    } finally {
      if (isMountedRef.current) {
        setIsEnding(false);
      }
    }
  }

  if (isLoading) {
    return (
      <PageFrame section="Production" title="Downtime Event" subtitle={messages("loading.default")}>
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          {messages("loading.default")}
        </div>
      </PageFrame>
    );
  }

  if (error || !event) {
    return (
      <PageFrame
        section="Production"
        title="Downtime Event"
        subtitle="The requested downtime event could not be loaded."
        action={
          <Link href="/downtime-events" style={sharedStyles.secondaryButton}>
            Back to Downtime Events
          </Link>
        }
      >
        <div style={sharedStyles.error} role="alert">
          {error ?? "Downtime event not found."}
        </div>
      </PageFrame>
    );
  }

  return (
    <PageFrame
      section="Production"
      title={`Downtime Event - ${fmt.dateTime(event.start_time)}`}
      subtitle="Downtime detail and linked production context."
      action={
        <Link href="/downtime-events" style={sharedStyles.secondaryButton}>
          Back to Downtime Events
        </Link>
      }
    >
      <section style={styles.panel}>
        <div style={styles.grid}>
          <DetailValue label="Start Time" value={fmt.dateTime(event.start_time)} />
          <DetailValue
            label="End Time"
            value={event.end_time ? fmt.dateTime(event.end_time) : "Still open"}
          />
          <DetailValue
            label="Duration"
            value={fmt.duration(event.duration_minutes)}
          />
          <div>
            <span style={styles.label}>Category</span>
            <DowntimeCategoryBadge category={event.category} />
          </div>
          <DetailValue label="Reason Code" value={event.reason_code ?? "Not specified"} />
          <div>
            <span style={styles.label}>Status</span>
            <DowntimeStatusBadge status={event.status} />
          </div>
        </div>

        <section style={styles.section} aria-label="References">
          <h2 style={{ margin: 0, fontSize: "18px" }}>References</h2>
          <ReferenceLine label="Work Center">
            <Link href={`/work-centers/${event.work_center_id}`} style={styles.link}>
              {formatWorkCenterLabel(workCenters, event.work_center_id)}
            </Link>
          </ReferenceLine>
          {event.shift_report_id ? (
            <ReferenceLine label="Shift Report">
              <Link href={`/shift-reports/${event.shift_report_id}`} style={styles.link}>
                {shiftReport ? fmt.date(shiftReport.report_date) : event.shift_report_id}
              </Link>
            </ReferenceLine>
          ) : null}
          {event.production_order_id ? (
            <ReferenceLine label="Production Order">
              <Link
                href={`/production-orders/${event.production_order_id}`}
                style={styles.link}
              >
                {formatProductionOrderLabel(productionOrders, event.production_order_id)}
              </Link>
            </ReferenceLine>
          ) : null}
        </section>

        <section style={styles.section} aria-label="Notes">
          <h2 style={{ margin: 0, fontSize: "18px" }}>Notes</h2>
          <p style={{ margin: 0 }}>{event.notes || "No notes recorded."}</p>
        </section>

        {event.status === "open" ? (
          <section style={styles.openAction} aria-label="End downtime">
            <div>
              <h2 style={{ margin: "0 0 6px", fontSize: "18px" }}>
                This event is still open
              </h2>
              <p style={{ margin: 0, color: "var(--text-muted)" }}>
                Provide an end time to close the event. Duration will be calculated by the backend.
              </p>
            </div>
            <form style={styles.actionRow} onSubmit={handleEndDowntime}>
              <label style={{ ...sharedStyles.field, minWidth: "240px" }}>
                <span style={sharedStyles.label}>End Time</span>
                <input
                  style={sharedStyles.input}
                  type="datetime-local"
                  value={endTime}
                  onChange={(changeEvent) => setEndTime(changeEvent.target.value)}
                  disabled={isEnding}
                  required
                />
              </label>
              <button style={sharedStyles.button} type="submit" disabled={isEnding}>
                {isEnding ? "Ending..." : "End Downtime"}
              </button>
            </form>
            {endError ? (
              <div style={sharedStyles.error} role="alert">
                {endError}
              </div>
            ) : null}
          </section>
        ) : null}
      </section>
    </PageFrame>
  );
}

function DetailValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span style={styles.label}>{label}</span>
      <p style={styles.value}>{value}</p>
    </div>
  );
}

function ReferenceLine({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <span style={styles.label}>{label}</span>
      <p style={styles.value}>{children}</p>
    </div>
  );
}
