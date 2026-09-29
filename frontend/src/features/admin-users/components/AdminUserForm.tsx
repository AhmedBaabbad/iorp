"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { listAdminRoles } from "@/features/admin-roles/api/admin-roles-api";
import type { AdminRoleListItem } from "@/features/admin-roles/types";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { ApiClientError } from "@/lib/api-client";
import { sharedStyles } from "@/styles/shared-styles";
import { createAdminUser, getAdminUser, updateAdminUser } from "../api/admin-users-api";

type Props = { userId?: string };

export function AdminUserForm({ userId }: Props) {
  const router = useRouter();
  const t = useTranslations("administration.users");
  const messages = useTranslations("messages");
  const isEdit = Boolean(userId);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [isOrganizationRoot, setIsOrganizationRoot] = useState(false);
  const [roles, setRoles] = useState<AdminRoleListItem[]>([]);
  const [roleCodes, setRoleCodes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const requests: Promise<unknown>[] = [listAdminRoles().then(setRoles)];
    if (userId) {
      requests.push(getAdminUser(userId).then((user) => {
        setFullName(user.full_name);
        setEmail(user.email);
        setPhone(user.phone ?? "");
        setIsOrganizationRoot(user.is_organization_root);
      }));
    }
    Promise.all(requests).catch((caught) => setError(getApiErrorMessage(caught, messages))).finally(() => setIsLoading(false));
  }, [messages, userId]);

  async function submit() {
    try {
      setError(null);
      setEmailError(null);
      const normalizedEmail = email.trim().toLowerCase();
      if (isEdit && userId) {
        await updateAdminUser(userId, {
          full_name: isOrganizationRoot ? undefined : fullName,
          email: isOrganizationRoot ? undefined : normalizedEmail,
          phone: phone || null,
        });
        router.push(`/admin/users/${userId}`);
      } else {
        const user = await createAdminUser({ full_name: fullName, email: normalizedEmail, phone: phone || null, password, role_codes: roleCodes });
        router.push(`/admin/users/${user.id}`);
      }
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.details && typeof caught.details === "object" && "code" in caught.details && caught.details.code === "EMAIL_ALREADY_EXISTS") {
        setEmailError(t("errors.emailAlreadyExists"));
        return;
      }
      setError(getApiErrorMessage(caught, messages));
    }
  }

  if (isLoading) return <PageFrame section={t("section")} title={isEdit ? t("editTitle") : t("createTitle")}><div style={sharedStyles.state}>{t("loadingDetail")}</div></PageFrame>;

  return (
    <PageFrame section={t("section")} title={isEdit ? t("editTitle") : t("createTitle")} subtitle={isEdit ? t("editSubtitle") : t("createSubtitle")}>
      {error ? <div style={sharedStyles.error}>{error}</div> : null}
      <form onSubmit={(e) => { e.preventDefault(); void submit(); }} style={{ display: "grid", gap: "16px", maxWidth: "520px" }}>
        {isOrganizationRoot ? <div style={sharedStyles.state} role="note">{t("rootFieldsReadOnly")}</div> : null}
        <label>{t("fields.fullName")}<input style={sharedStyles.input} value={fullName} onChange={(e) => setFullName(e.target.value)} disabled={isOrganizationRoot} required /></label>
        <label>{t("fields.email")}<input style={sharedStyles.input} type="email" value={email} onChange={(e) => { setEmail(e.target.value); setEmailError(null); }} disabled={isOrganizationRoot} required />{emailError ? <span style={{ color: "var(--danger)", fontSize: "13px" }} role="alert">{emailError}</span> : <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>{t("errors.emailGloballyUnique")}</span>}</label>
        <label>{t("fields.phone")}<input style={sharedStyles.input} type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} /></label>
        {!isEdit ? <label>{t("fields.password")}<input style={sharedStyles.input} type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required /></label> : null}
        {!isEdit ? (
          <fieldset><legend>{t("fields.roles")}</legend>{roles.map((role) => <label key={role.id} style={{ display: "block" }}><input type="checkbox" checked={roleCodes.includes(role.code)} onChange={(e) => setRoleCodes(e.target.checked ? [...roleCodes, role.code] : roleCodes.filter((code) => code !== role.code))} /> {role.name}</label>)}</fieldset>
        ) : null}
        <button style={sharedStyles.button} type="submit">{isEdit ? t("updateButton") : t("createButton")}</button>
      </form>
    </PageFrame>
  );
}
