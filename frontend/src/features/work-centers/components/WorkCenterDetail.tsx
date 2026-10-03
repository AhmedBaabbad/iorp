"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { useFormatter } from "@/hooks/useFormatter";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { deleteWorkCenter, getWorkCenterById } from "../api/work-centers-api";
import type { WorkCenterData } from "../types";
import {
  formatWorkCenterStatus,
  formatWorkCenterType,
  statusBadgeStyle,
  typeBadgeStyle,
} from "./work-center-utils";
import { usePermission } from "@/features/auth/permission-hooks";
import { P } from "@/lib/production-permissions";

const styles: Record<string, CSSProperties> = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "var(--overlay)",
    backdropFilter: "blur(2px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modal: {
    background: "var(--surface)",
    borderRadius: "14px",
    boxShadow: "0 24px 64px rgba(15, 23, 42, 0.28), 0 4px 16px rgba(15, 23, 42, 0.12)",
    padding: "32px",
    maxWidth: "460px",
    width: "90%",
    display: "grid",
    gap: "20px",
  },
  modalIcon: {
    width: "48px",
    height: "48px",
    borderRadius: "50%",
    background: "var(--surface-muted)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "22px",
    margin: "0 auto",
  },
  modalTitle: {
    fontSize: "18px",
    fontWeight: 700,
    color: "var(--text)",
    margin: 0,
    textAlign: "center" as const,
  },
  modalBody: {
    fontSize: "14px",
    color: "var(--text-muted)",
    margin: 0,
    lineHeight: "1.7",
    textAlign: "center" as const,
  },
  modalActions: {
    display: "flex",
    gap: "12px",
    justifyContent: "center",
    flexWrap: "wrap" as const,
  },
  modalCancelButton: {
    ...sharedStyles.secondaryButton,
    minHeight: "40px",
    padding: "10px 24px",
    fontSize: "14px",
  },
  modalDeleteButton: {
    background: "var(--danger)",
    border: "none",
    borderRadius: "8px",
    color: "var(--on-accent)",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: 600,
    minHeight: "40px",
    padding: "10px 24px",
  },
  headerActions: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap" as const,
  },
  deleteButton: {
    ...sharedStyles.secondaryButton,
    borderColor: "color-mix(in srgb, var(--danger) 35%, var(--surface))",
    color: "var(--danger)",
  },
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

export function WorkCenterDetail() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const t = useTranslations("production.workCenters");
  const canUpdate = usePermission(P.WORK_CENTERS_UPDATE);
  const canDelete = usePermission(P.WORK_CENTERS_DELETE);
  const tEnums = useTranslations();
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const workCenterId = params.id;
  const [workCenter, setWorkCenter] = useState<WorkCenterData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSuccessRedirect, setDeleteSuccessRedirect] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const data = await getWorkCenterById(workCenterId);
        if (isMounted) setWorkCenter(data);
      } catch (caughtError) {
        if (!isMounted) return;
        if (caughtError instanceof ApiClientError && caughtError.status === 404) {
          setIsNotFound(true);
          return;
        }
        setError(getApiErrorMessage(caughtError, messages));
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    void load();
    return () => { isMounted = false; };
  }, [workCenterId]);

  async function handleConfirmDelete() {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteWorkCenter(workCenterId);
      setDeleteSuccessRedirect("/work-centers");
    } catch (caughtError) {
      setDeleteError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <>
      {deleteSuccessRedirect ? (
        <SuccessModal
          message={t("deleteSuccess")}
          okLabel={common("actions.ok")}
          onOk={() => router.replace(deleteSuccessRedirect)}
        />
      ) : null}

      {showDeleteConfirm ? (
        <div style={styles.backdrop} onClick={() => setShowDeleteConfirm(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalIcon}>!</div>
            <h2 style={styles.modalTitle}>{t("deleteConfirmTitle")}</h2>
            <p style={styles.modalBody}>{t("deleteConfirm")}</p>
            {deleteError ? (
              <div style={sharedStyles.error} role="alert">{deleteError}</div>
            ) : null}
            <div style={styles.modalActions}>
              <button
                type="button"
                style={styles.modalCancelButton}
                onClick={() => setShowDeleteConfirm(false)}
                disabled={isDeleting}
              >
                {common("actions.cancel")}
              </button>
              <button
                type="button"
                style={styles.modalDeleteButton}
                onClick={() => void handleConfirmDelete()}
                disabled={isDeleting}
              >
                {common("actions.delete")}
              </button>
            </div>
          </div>
        </div>
      ) : null}

<PageFrame
        section="Production"
        title={workCenter?.name ?? t("detailTitle")}
        subtitle={workCenter ? workCenter.code : t("detailSubtitle")}
        action={
          <div style={styles.headerActions}>
            {workCenter && canUpdate ? (
              <Link
                href={`/work-centers/${workCenterId}/edit`}
                style={sharedStyles.secondaryButton}
              >
                {common("actions.edit")}
              </Link>
            ) : null}
            {workCenter && canDelete ? (
              <button
                type="button"
                style={styles.deleteButton}
                onClick={() => setShowDeleteConfirm(true)}
              >
                {common("actions.delete")}
              </button>
            ) : null}
            <Link href="/work-centers" style={sharedStyles.secondaryButton}>
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
            <p style={{ margin: "0 0 18px" }}>{t("notFoundDescription")}</p>
            <Link href="/work-centers" style={sharedStyles.button}>{t("returnToList")}</Link>
          </section>
        ) : null}

        {!isLoading && error ? (
          <div style={sharedStyles.error} role="alert">{error}</div>
        ) : null}

        {!isLoading && !error && !isNotFound && workCenter ? (
          <section style={styles.detailGrid} aria-label={t("detailsAria")}>
            <DetailItem label={t("fields.centerCode")} value={workCenter.code} />
            <DetailItem label={t("fields.name")} value={workCenter.name} />
            <DetailItem
              label={t("fields.centerType")}
              value={
                <span style={typeBadgeStyle(workCenter.center_type)}>
                  {formatWorkCenterType(workCenter.center_type, tEnums)}
                </span>
              }
            />
            <DetailItem
              label={t("fields.status")}
              value={
                <span style={statusBadgeStyle(workCenter.status)}>
                  {formatWorkCenterStatus(workCenter.status, tEnums)}
                </span>
              }
            />
            <DetailItem label={t("fields.location")} value={workCenter.location} />
            <DetailItem
              label={t("fields.commissionedDate")}
              value={workCenter.commissioned_date ? fmt.date(workCenter.commissioned_date) : null}
            />
            <DetailItem
              label={t("fields.createdAt")}
              value={fmt.date(workCenter.created_at)}
            />
            <DetailItem label={t("fields.notes")} value={workCenter.notes} />
          </section>
        ) : null}
      </PageFrame>
    </>
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
