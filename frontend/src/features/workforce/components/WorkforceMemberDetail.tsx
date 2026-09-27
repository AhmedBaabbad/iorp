"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { usePermission } from "@/features/auth";
import { useEnumLabel } from "@/i18n/enum-helpers";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import {
  deleteWorkforceMember,
  getWorkforceMemberById,
  getWorkforceMembers,
  getUsers,
  linkUserToMember,
  unlinkUserFromMember,
} from "../api/workforce-api";
import type { WorkforceMember } from "../types";
import type { AdminUserListItem } from "@/features/admin-users/types";
import { WorkforceMemberStatusBadge } from "./WorkforceMemberStatusBadge";
import { WorkforceMemberTypeBadge } from "./WorkforceMemberTypeBadge";
import { useFormatter } from "@/hooks/useFormatter";

const styles: Record<string, CSSProperties> = {
  headerActions: { display: "flex", gap: "8px", flexWrap: "wrap" },
  deleteButton: { ...sharedStyles.secondaryButton, borderColor: "#fecdd3", color: "#be123c" },
  detailGrid: {
    display: "grid",
    gap: "1px",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    background: "#e4e7ec",
    borderRadius: "8px",
    overflow: "hidden",
  },
  detailItem: { background: "#ffffff", padding: "18px" },
  detailLabel: { color: "#52606d", fontSize: "13px", fontWeight: 700, margin: "0 0 8px" },
  detailValue: { margin: 0, overflowWrap: "anywhere" },
  linkPanel: {
    background: "#ffffff",
    border: "1px solid #d9dee7",
    borderRadius: "8px",
    display: "grid",
    gap: "12px",
    marginTop: "18px",
    padding: "18px",
  },
  linkTitle: { fontSize: "18px", margin: 0 },
  linkSubtitle: { color: "#52606d", margin: 0 },
  linkActions: { display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center" },
  success: {
    background: "#dcfce7",
    border: "1px solid #bbf7d0",
    borderRadius: "6px",
    color: "#166534",
    fontSize: "14px",
    padding: "12px 14px",
  },
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(15, 23, 42, 0.55)",
    backdropFilter: "blur(2px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modal: {
    background: "#ffffff",
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
    background: "#fff1f2",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "22px",
    margin: "0 auto",
  },
  modalTitle: {
    fontSize: "18px",
    fontWeight: 700,
    color: "#0f172a",
    margin: 0,
    textAlign: "center" as const,
  },
  modalBody: {
    fontSize: "14px",
    color: "#475569",
    margin: 0,
    lineHeight: "1.7",
    textAlign: "center" as const,
  },
  modalWarning: {
    fontSize: "13px",
    fontWeight: 600,
    color: "#be123c",
    textAlign: "center" as const,
    margin: 0,
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
    background: "#be123c",
    border: "none",
    borderRadius: "8px",
    color: "#ffffff",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: 600,
    minHeight: "40px",
    padding: "10px 24px",
  },
};

export function WorkforceMemberDetail() {
  const params = useParams<{ id: string }>();
  const memberId = params.id;
  const router = useRouter();
  const t = useTranslations("workforce.members");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const enumLabel = useEnumLabel();
  const fmt = useFormatter();
  const canUpdate = usePermission("workforce:members:update");
  const canDelete = usePermission("workforce:members:delete");
  const canLinkUser = usePermission("workforce:members:link_user");
  const [member, setMember] = useState<WorkforceMember | null>(null);
  const [userId, setUserId] = useState("");
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [linkedElsewhereUserIds, setLinkedElsewhereUserIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingLink, setIsSavingLink] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [linkMessage, setLinkMessage] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [deleteSuccessRedirect, setDeleteSuccessRedirect] = useState<string | null>(null);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isUnlinkConfirmOpen, setIsUnlinkConfirmOpen] = useState(false);

  async function loadMember() {
    try {
      setIsLoading(true);
      setError(null);
      setIsNotFound(false);
      const [response, availableUsers, allMembers] = await Promise.all([
        getWorkforceMemberById(memberId),
        getUsers(),
        getWorkforceMembers(),
      ]);
      setMember(response);
      setUsers(availableUsers);
      setUserId(response.user_id ?? "");
      setLinkedElsewhereUserIds(
        new Set(
          allMembers
            .filter((otherMember) => otherMember.id !== memberId && otherMember.user_id)
            .map((otherMember) => otherMember.user_id as string),
        ),
      );
    } catch (caughtError) {
      if (caughtError instanceof ApiClientError && caughtError.status === 404) {
        setIsNotFound(true);
        return;
      }
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadMember();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memberId]);

  const eligibleUsers = useMemo(
    () => users.filter((user) => user.status === "active" && !linkedElsewhereUserIds.has(user.id)),
    [users, linkedElsewhereUserIds],
  );

  function handleDeleteClick() {
    setIsDeleteConfirmOpen(true);
    setDeleteError(null);
  }

  function handleCancelDelete() {
    if (isDeleting) return;
    setIsDeleteConfirmOpen(false);
    setDeleteError(null);
  }

  async function handleConfirmDelete() {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteWorkforceMember(memberId);
      setIsDeleteConfirmOpen(false);
      setDeleteSuccessRedirect("/workforce");
    } catch (caughtError) {
      setDeleteError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleLinkUser() {
    setIsSavingLink(true);
    setError(null);
    setLinkMessage(null);
    try {
      const response = await linkUserToMember(memberId, userId);
      setMember(response);
      setUserId(response.user_id ?? "");
      setLinkMessage(t("linkSuccess"));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSavingLink(false);
    }
  }

  function handleUnlinkClick() {
    setError(null);
    setIsUnlinkConfirmOpen(true);
  }

  function handleCancelUnlink() {
    if (isSavingLink) return;
    setIsUnlinkConfirmOpen(false);
  }

  async function handleConfirmUnlink() {
    setIsSavingLink(true);
    setError(null);
    setLinkMessage(null);
    try {
      const response = await unlinkUserFromMember(memberId);
      setMember(response);
      setUserId("");
      setIsUnlinkConfirmOpen(false);
      setLinkMessage(t("unlinkSuccess"));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSavingLink(false);
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
      {isDeleteConfirmOpen && member ? (
        <div style={styles.backdrop} onClick={!isDeleting ? handleCancelDelete : undefined}>
          <div style={styles.modal} onClick={(event) => event.stopPropagation()}>
            <div style={styles.modalIcon}>!</div>
            <h2 style={styles.modalTitle}>{t("deleteConfirmTitle")}</h2>
            <p style={styles.modalBody}>
              {t("deleteConfirmMessage", { name: member.full_name })}
            </p>
            <p style={styles.modalWarning}>{t("deleteWarning")}</p>
            {deleteError ? (
              <div style={sharedStyles.error} role="alert">
                {deleteError}
              </div>
            ) : null}
            <div style={styles.modalActions}>
              <button
                type="button"
                style={styles.modalCancelButton}
                onClick={handleCancelDelete}
                disabled={isDeleting}
              >
                {t("deleteCancelButton")}
              </button>
              <button
                type="button"
                style={styles.modalDeleteButton}
                onClick={() => void handleConfirmDelete()}
                disabled={isDeleting}
              >
                {isDeleting ? messages("loading.deleting") : t("deleteConfirmButton")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {isUnlinkConfirmOpen && member ? (
        <div style={styles.backdrop} onClick={!isSavingLink ? handleCancelUnlink : undefined}>
          <div style={styles.modal} onClick={(event) => event.stopPropagation()}>
            <div style={styles.modalIcon}>!</div>
            <h2 style={styles.modalTitle}>{t("unlinkUserButton")}</h2>
            <p style={styles.modalBody}>{t("unlinkConfirm")}</p>
            {error ? (
              <div style={sharedStyles.error} role="alert">
                {error}
              </div>
            ) : null}
            <div style={styles.modalActions}>
              <button
                type="button"
                style={styles.modalCancelButton}
                onClick={handleCancelUnlink}
                disabled={isSavingLink}
              >
                {t("deleteCancelButton")}
              </button>
              <button
                type="button"
                style={styles.modalDeleteButton}
                onClick={() => void handleConfirmUnlink()}
                disabled={isSavingLink}
              >
                {isSavingLink ? messages("loading.saving") : t("unlinkUserButton")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <PageFrame
        section="Workforce"
        title={member?.full_name ?? t("detailTitle")}
        subtitle={member ? member.employee_code : t("detailSubtitle")}
        action={
          <div style={styles.headerActions}>
            {member && canUpdate ? (
              <Link href={`/workforce/${memberId}/edit`} style={sharedStyles.secondaryButton}>
                {common("actions.edit")}
              </Link>
            ) : null}
            {member && canDelete ? (
              <button type="button" style={styles.deleteButton} onClick={handleDeleteClick}>
                {common("actions.delete")}
              </button>
            ) : null}
            <Link href="/workforce" style={sharedStyles.secondaryButton}>
              {t("backToList")}
            </Link>
          </div>
        }
      >
        {isLoading ? (
          <div style={{ ...sharedStyles.state, background: "#ffffff" }}>{t("loadingDetail")}</div>
        ) : null}

        {!isLoading && isNotFound ? (
          <section style={{ ...sharedStyles.state, background: "#ffffff" }}>
            <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
            <p style={{ margin: "0 0 18px" }}>{t("notFoundDescription")}</p>
            <Link href="/workforce" style={sharedStyles.button}>{t("returnToList")}</Link>
          </section>
        ) : null}

        {!isLoading && error && !isUnlinkConfirmOpen ? (
          <div style={sharedStyles.error} role="alert">{error}</div>
        ) : null}
        {linkMessage ? <div style={styles.success} role="status">{linkMessage}</div> : null}

        {!isLoading && !isNotFound && member ? (
          <>
            <section style={styles.detailGrid} aria-label={t("detailsAria")}>
              <DetailItem label={t("fields.employeeCode")} value={member.employee_code} />
              <DetailItem label={t("fields.fullName")} value={member.full_name} />
              <DetailItem label={t("fields.displayName")} value={member.display_name} />
              <DetailItem
                label={t("fields.workerType")}
                value={<WorkforceMemberTypeBadge workerType={member.worker_type} />}
              />
              <DetailItem
                label={t("fields.employmentType")}
                value={enumLabel("workforceMember", "employmentType", member.employment_type)}
              />
              <DetailItem
                label={t("fields.status")}
                value={<WorkforceMemberStatusBadge status={member.status} />}
              />
              <DetailItem label={t("fields.phone")} value={member.phone} />
              <DetailItem label={t("fields.email")} value={member.email} />
              <DetailItem
                label={t("fields.isSystemUser")}
                value={member.is_system_user ? t("systemUserYes") : t("systemUserNo")}
              />
              <DetailItem label={t("fields.primarySkill")} value={member.primary_skill} />
              <DetailItem label={t("fields.createdAt")} value={fmt.date(member.created_at)} />
              <DetailItem label={t("fields.updatedAt")} value={fmt.date(member.updated_at)} />
              <DetailItem label={t("fields.notes")} value={member.notes} />
            </section>

            <section style={styles.linkPanel}>
              <h2 style={styles.linkTitle}>{t("systemAccountSection")}</h2>
              {member.linked_user ? (
                <>
                  <p style={styles.linkSubtitle}>{t("linked")}</p>
                  <DetailItem
                    label={t("linkedUserLabel")}
                    value={`${member.linked_user.full_name} (${member.linked_user.email})`}
                  />
                  {canLinkUser ? (
                    <div style={styles.linkActions}>
                      <button
                        type="button"
                        style={sharedStyles.secondaryButton}
                        disabled={isSavingLink}
                        onClick={handleUnlinkClick}
                      >
                        {t("unlinkUserButton")}
                      </button>
                    </div>
                  ) : null}
                </>
              ) : (
                <>
                  <p style={styles.linkSubtitle}>{t("notLinked")}</p>
                  {canLinkUser ? (
                    <>
                      <p style={styles.linkSubtitle}>{t("linkUserTitle")}</p>
                      <div style={styles.linkActions}>
                        <select
                          style={{ ...sharedStyles.input, maxWidth: "420px" }}
                          value={userId}
                          onChange={(event) => setUserId(event.target.value)}
                          disabled={isSavingLink}
                        >
                          <option value="">{t("selectUserPlaceholder")}</option>
                          {eligibleUsers.map((user) => (
                            <option key={user.id} value={user.id}>
                              {user.full_name} ({user.email})
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          style={sharedStyles.button}
                          disabled={isSavingLink || !userId}
                          onClick={() => void handleLinkUser()}
                        >
                          {t("linkUserButton")}
                        </button>
                      </div>
                    </>
                  ) : null}
                </>
              )}
            </section>
          </>
        ) : null}
      </PageFrame>
    </>
  );
}

function DetailItem({ label, value }: { label: string; value: string | number | null | ReactNode }) {
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
