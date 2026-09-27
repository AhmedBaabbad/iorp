"use client";

import type { CSSProperties } from "react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { SectionShell } from "@/components/layout/section-shell";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getDefectsByCheck } from "../api/quality-defects-api";
import type { QualityDefectListItem } from "../types";
import { DefectCategoryBadge } from "./DefectCategoryBadge";
import { DefectSeverityBadge } from "./DefectSeverityBadge";
import { truncateText } from "./quality-defect-utils";
import { QualityDefectForm } from "./QualityDefectForm";

type QualityDefectsListProps = {
  qualityCheckId: string;
  checkStatus: string;
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
};

export function QualityDefectsList({
  qualityCheckId,
  checkStatus,
}: QualityDefectsListProps) {
  const t = useTranslations("quality.qualityChecks.defects");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [defects, setDefects] = useState<QualityDefectListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const isMountedRef = useRef(true);
  const isClosed = checkStatus === "closed";

  const loadDefects = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await getDefectsByCheck(qualityCheckId);
      if (isMountedRef.current) {
        setDefects(response);
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
  }, [qualityCheckId, t]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadDefects();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadDefects]);

  async function handleDefectCreated() {
    await loadDefects();
    setIsFormOpen(false);
  }

  return (
    <SectionShell
      titleId="quality-defects-title"
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
        <QualityDefectForm
          qualityCheckId={qualityCheckId}
          onCreated={handleDefectCreated}
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
            onClick={() => void loadDefects()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && defects.length === 0 ? (
        <div style={sharedStyles.state}>{t("empty")}</div>
      ) : null}

      {!isLoading && !error && defects.length > 0 ? (
        <div style={sharedStyles.list}>
          {defects.map((defect) => (
            <article key={defect.id} style={sharedStyles.item}>
              <div style={sharedStyles.itemHeader}>
                <div>
                  <h3 style={sharedStyles.itemTitle}>{fmt.date(defect.defect_date)}</h3>
                  <div style={styles.itemMetaRow}>
                    <DefectCategoryBadge category={defect.defect_category} />
                    <DefectSeverityBadge severity={defect.severity} />
                    <span style={sharedStyles.meta}>
                      {fmt.number(defect.defect_count)} {defect.defect_count === 1 ? t("unitSingular") : t("unitPlural")}
                    </span>
                  </div>
                </div>
              </div>

              <p style={sharedStyles.text}>
                {truncateText(defect.description, 180)}
              </p>
            </article>
          ))}
        </div>
      ) : null}
    </SectionShell>
  );
}
