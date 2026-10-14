"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { listAdminRoles } from "@/features/admin-roles/api/admin-roles-api";
import type { AdminRoleListItem } from "@/features/admin-roles/types";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { ApiClientError } from "@/lib/api-client";
import { useNotify } from "@/components/notify/Notifications";
import { sharedStyles } from "@/styles/shared-styles";
import { createAdminUser } from "../api/admin-users-api";

export function AdminUserForm() {
  const router = useRouter();
  const t = useTranslations("administration.users");
  const messages = useTranslations("messages");
  const notify = useNotify();
  const [preferredLocale, setPreferredLocale] = useState<"ar" | "en">("ar");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [roles, setRoles] = useState<AdminRoleListItem[]>([]);
  const [roleCodes, setRoleCodes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const requests: Promise<unknown>[] = [listAdminRoles().then(setRoles)];
    Promise.all(requests).catch((caught) => setError(getApiErrorMessage(caught, messages))).finally(() => setIsLoading(false));
  }, [messages]);

  async function submit() {
    try {
      setError(null);
      setEmailError(null);
      const normalizedEmail = email.trim().toLowerCase();
        const user = await createAdminUser({ full_name: fullName, email: normalizedEmail, phone: phone || null, role_codes: roleCodes, preferred_locale: preferredLocale });
        // SEC-003: the new user chooses their own password through the e-mailed activation link
        if (user.invitation_sent) notify.success(t("invitation.sent", { email: user.email }));
        else notify.error(t("invitation.notSent"));
        router.push(`/admin/users/${user.id}`);
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.details && typeof caught.details === "object" && "code" in caught.details && caught.details.code === "EMAIL_ALREADY_EXISTS") {
        setEmailError(t("errors.emailAlreadyExists"));
        return;
      }
      setError(getApiErrorMessage(caught, messages));
    }
  }

  if (isLoading) return <PageFrame section={t("section")} title={t("createTitle")}><div style={sharedStyles.state}>{t("loadingDetail")}</div></PageFrame>;

  return (
    <PageFrame section={t("section")} title={t("createTitle")} subtitle={t("createSubtitle")}>
      {error ? <div style={sharedStyles.error}>{error}</div> : null}
      <form onSubmit={(e) => { e.preventDefault(); void submit(); }} style={{ display: "grid", gap: "16px", maxWidth: "520px" }}>
        <label>{t("fields.fullName")}<input style={sharedStyles.input} value={fullName} onChange={(e) => setFullName(e.target.value)} required /></label>
        <label>{t("fields.email")}<input style={sharedStyles.input} type="email" value={email} onChange={(e) => { setEmail(e.target.value); setEmailError(null); }} required />{emailError ? <span style={{ color: "var(--danger)", fontSize: "13px" }} role="alert">{emailError}</span> : <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>{t("errors.emailGloballyUnique")}</span>}</label>
        <label>{t("fields.phone")}<input style={sharedStyles.input} type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} /></label>
        <label>{t("fields.preferredLocale")}<select style={sharedStyles.input} value={preferredLocale} onChange={event => setPreferredLocale(event.target.value as "ar" | "en")}><option value="ar">العربية</option><option value="en">English</option></select></label>
        <div style={sharedStyles.state} role="note">{t("invitation.note")}</div>
          <fieldset><legend>{t("fields.roles")}</legend>{roles.map((role) => <label key={role.id} style={{ display: "block" }}><input type="checkbox" checked={roleCodes.includes(role.code)} onChange={(e) => setRoleCodes(e.target.checked ? [...roleCodes, role.code] : roleCodes.filter((code) => code !== role.code))} /> {role.name}</label>)}</fieldset>
        <button style={sharedStyles.button} type="submit">{t("createButton")}</button>
      </form>
    </PageFrame>
  );
}
