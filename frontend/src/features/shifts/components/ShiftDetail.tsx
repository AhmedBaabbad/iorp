"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { getShiftById } from "../api/shifts-api";
import type { ShiftData } from "../types";
import {
  formatShiftStatus,
  formatShiftType,
  formatTimeRange,
  statusBadgeStyle,
  typeBadgeStyle,
} from "./shift-utils";


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
};

export function ShiftDetail() {
  const t = useTranslations("production.shifts");
  const tEnums = useTranslations();
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const params = useParams<{ id: string }>();
  const shiftId = params.id;
  const [shift, setShift] = useState<ShiftData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadShift() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const shiftResponse = await getShiftById(shiftId);

        if (isMounted) {
          setShift(shiftResponse);
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

    void loadShift();

    return () => {
      isMounted = false;
    };
  }, [shiftId, t, messages]);


  return (
    <PageFrame
      section="Production"
      title={shift?.name ?? t("detailTitle")}
      subtitle={shift ? shift.code : t("detailSubtitle")}
      action={
        <div style={{ display: "flex", gap: "8px" }}>
          <Link href={`/shifts/${shiftId}/edit`} style={sharedStyles.button}>
            {common("actions.edit")}
          </Link>
          <Link href="/shifts" style={sharedStyles.secondaryButton}>
            {t("backToList")}
          </Link>
        </div>
      }
    >
      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          {t("loadingDetail")}
        </div>
      ) : null}

      {!isLoading && isNotFound ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
          <p style={{ margin: "0 0 18px" }}>
            {t("notFoundDescription")}
          </p>
          <Link href="/shifts" style={sharedStyles.button}>
            {t("returnToList")}
          </Link>
        </section>
      ) : null}

      {!isLoading && error ? (
        <div style={sharedStyles.error} role="alert">
          {error}
        </div>
      ) : null}

      {!isLoading && !error && !isNotFound && shift ? (
        <section style={styles.detailGrid} aria-label={t("detailTitle")}>
          <DetailItem label={t("fields.code")} value={shift.code} />
          <DetailItem label={t("fields.name")} value={shift.name} />
          <DetailItem
            label={t("fields.type")}
            value={
              <span style={typeBadgeStyle(shift.shift_type)}>
                {formatShiftType(shift.shift_type, tEnums)}
              </span>
            }
          />
          <DetailItem
            label={t("fields.time")}
            value={formatTimeRange(shift.start_time, shift.end_time)}
          />
          <DetailItem
            label={t("fields.crossesMidnight")}
            value={shift.crosses_midnight ? t("yesSpansMidnight") : t("doesNotSpanMidnight")}
          />
          <DetailItem
            label={t("fields.status")}
            value={
              <span style={statusBadgeStyle(shift.status)}>
                {formatShiftStatus(shift.status, tEnums)}
              </span>
            }
          />
          <DetailItem label={t("fields.notes")} value={shift.notes} />
        </section>
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
