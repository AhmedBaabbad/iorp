"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getAdminRole } from "../api/admin-roles-api";
import type { AdminRoleDetail as AdminRoleDetailType } from "../types";
import { AdminRolePermissionsManager } from "./AdminRolePermissionsManager";

import styles from "./roles.module.css";

export function AdminRoleDetail() {
  const params = useParams<{ id: string }>();
  const t = useTranslations("administration.roles");
  const messages = useTranslations("messages");
  const canWrite = usePermission("foundation:roles:write");
  const [role, setRole] = useState<AdminRoleDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(true);
    getAdminRole(params.id)
      .then(setRole)
      .catch((caughtError) => setError(getApiErrorMessage(caughtError, messages)))
      .finally(() => setIsLoading(false));
  }, [messages, params.id]);

  if (isLoading) {
    return <p>{t("loadingDetail")}</p>;
  }

  return (
    <PageFrame
      section={t("section")}
      title={role ? (role.is_system && t.has(`systemRoleNames.${role.code}`) ? t(`systemRoleNames.${role.code}`) : role.name) : t("detailTitle")}
      action={role && canWrite && role.is_editable ? <Link href={`/admin/roles/${role.id}/edit`} style={sharedStyles.button}>{t("updateButton")}</Link> : null}
    >
      {error ? <div style={sharedStyles.error}>{error}</div> : null}
      {role ? (
        <div style={{ display: "grid", gap: "16px" }}>
          <section className={styles.roleCard}>
            <div className={styles.stats}><span className={styles.badge}>{role.is_system ? t("systemBadge") : t("customBadge")}</span>{role.is_protected ? <span className={styles.badge}>{t("protectedBadge")}</span> : null}</div>
            <p>{role.is_system && t.has(`systemRoleDescriptions.${role.code}`) ? t(`systemRoleDescriptions.${role.code}`) : role.description ?? "-"}</p>
            <code dir="ltr">{role.code}</code>
            <div className={styles.stats}><div className={styles.stat}><strong>{role.user_count}</strong><span>{t("fields.userCount")}</span></div><div className={styles.stat}><strong>{role.permission_count}</strong><span>{t("fields.permissionCount")}</span></div></div>
            {!role.is_editable ? <p>{t("systemEditBlocked")}</p> : null}
          </section>
          <AdminRolePermissionsManager roleId={role.id} readOnly={!role.is_editable} />
          <Link href="/admin/roles" style={sharedStyles.secondaryButton}>{t("backToList")}</Link>
        </div>
      ) : null}
    </PageFrame>
  );
}
