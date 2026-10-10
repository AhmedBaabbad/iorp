"use client";

import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { SectionShell } from "@/components/layout/section-shell";
import { useFormatter } from "@/hooks/useFormatter";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { deleteSampleEvaluation, listSampleEvaluations } from "../api/sample-evaluations-api";
import { usePermission } from "@/features/auth/permission-hooks";
import type {
  SampleEvaluationListItem,
  SampleEvaluationNextAction,
} from "../types";
import { SampleEvaluationResultBadge } from "./SampleEvaluationResultBadge";
import { SampleEvaluationForm } from "./SampleEvaluationForm";

type SampleEvaluationsListProps = {
  sampleId: string;
};

const styles: Record<string, CSSProperties> = {
  itemMetaRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
    alignItems: "center",
  },
};

export function SampleEvaluationsList({ sampleId }: SampleEvaluationsListProps) {
  const tEnums = useTranslations();
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const t = useTranslations("commercial.samples.evaluations");
  const fmt = useFormatter();
  const [evaluations, setEvaluations] = useState<SampleEvaluationListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  // RBAC-002: adding, correcting and removing an evaluation are separate permissions.
  const canCreate = usePermission("commercial:evaluations:create");
  const canUpdate = usePermission("commercial:evaluations:update");
  const canDelete = usePermission("commercial:evaluations:delete");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function remove(id: string) {
    setBusyId(id);
    try { await deleteSampleEvaluation(id); setConfirmingId(null); await loadEvaluations(); }
    catch (caughtError) { setError(getApiErrorMessage(caughtError, messages)); }
    finally { setBusyId(null); }
  }
  const isMountedRef = useRef(true);

  const loadEvaluations = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await listSampleEvaluations(sampleId);
      if (isMountedRef.current) {
        setEvaluations(response);
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
  }, [sampleId, messages]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadEvaluations();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadEvaluations]);

  async function handleCreated() {
    setIsFormOpen(false);
    await loadEvaluations();
  }

  return (
    <SectionShell
      titleId="sample-evaluations-title"
      title={t("sectionTitle")}
      subtitle={t("sectionDescription")}
    >
      {canCreate ? (
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button
            style={sharedStyles.secondaryButton}
            type="button"
            onClick={() => setIsFormOpen((current) => !current)}
          >
            {isFormOpen ? t("cancelAdd") : t("addButton")}
          </button>
        </div>
      ) : null}

      {isFormOpen ? <SampleEvaluationForm sampleId={sampleId} onCreated={handleCreated} /> : null}

      {isLoading ? <div style={sharedStyles.state}>{t("loading")}</div> : null}

      {!isLoading && error ? (
        <div style={{ display: "grid", gap: "12px" }}>
          <div style={sharedStyles.error} role="alert">
            {error}
          </div>
          <button
            style={{ ...sharedStyles.secondaryButton, width: "fit-content" }}
            type="button"
            onClick={() => void loadEvaluations()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && evaluations.length === 0 && !isFormOpen ? (
        <div style={sharedStyles.state}>{t("empty")}</div>
      ) : null}

      {!isLoading && !error && evaluations.length > 0 ? (
        <div style={sharedStyles.list}>
          {evaluations.map((evaluation) => (
            <article key={evaluation.id} style={sharedStyles.item}>
              <div style={sharedStyles.itemHeader}>
                <div>
                  <h3 style={sharedStyles.itemTitle}>
                    {fmt.date(evaluation.evaluation_date)}
                  </h3>
                  <div style={styles.itemMetaRow}>
                    <SampleEvaluationResultBadge resultStatus={evaluation.result_status} />
                    <span style={sharedStyles.meta}>
                      {formatNextAction(evaluation.next_action, tEnums)}
                    </span>
                  </div>
                </div>
              </div>

              <p style={sharedStyles.text}>
                {displayValue(truncateText(evaluation.comments, 180))}
              </p>
              <p style={sharedStyles.meta}>
                {t("labels.evaluatedBy", { value: displayValue(evaluation.evaluated_by_name) })}
              </p>
              {editingId === evaluation.id ? (
                <SampleEvaluationForm sampleId={sampleId} evaluation={evaluation}
                  onCreated={async () => { setEditingId(null); await loadEvaluations(); }} />
              ) : null}
              {(canUpdate || canDelete) ? (
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  {canUpdate ? (
                    <button type="button" style={sharedStyles.secondaryButton} disabled={busyId !== null}
                      onClick={() => setEditingId((current) => (current === evaluation.id ? null : evaluation.id))}>
                      {editingId === evaluation.id ? common("actions.cancel") : common("actions.edit")}
                    </button>
                  ) : null}
                  {canDelete && confirmingId !== evaluation.id ? (
                    <button type="button" style={sharedStyles.secondaryButton} disabled={busyId !== null} onClick={() => setConfirmingId(evaluation.id)}>
                      {common("actions.delete")}
                    </button>
                  ) : null}
                  {canDelete && confirmingId === evaluation.id ? (
                    <>
                      <span style={sharedStyles.meta}>{t("deleteConfirm")}</span>
                      <button type="button" style={{ ...sharedStyles.button, background: "var(--danger)", borderColor: "var(--danger)" }}
                        disabled={busyId !== null} onClick={() => void remove(evaluation.id)}>{t("deleteYes")}</button>
                      <button type="button" style={sharedStyles.secondaryButton} disabled={busyId !== null} onClick={() => setConfirmingId(null)}>
                        {common("actions.cancel")}
                      </button>
                    </>
                  ) : null}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
    </SectionShell>
  );
}

function formatNextAction(value: SampleEvaluationNextAction, t: (key: string) => string) {
  return getEnumLabel("sampleEvaluation", "nextAction", value, t);
}

function truncateText(value: string | null, maxLength: number) {
  if (!value || value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, maxLength - 1)}...`;
}

