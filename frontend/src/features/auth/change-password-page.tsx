"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";
import { PageFrame } from "@/components/layout/page-frame";
import { PasswordInput } from "@/components/PasswordInput";
import { ApiClientError } from "@/lib/api-client";
import { sharedStyles } from "@/styles/shared-styles";
import { changePassword } from "./auth-client";
import { useAuth } from "./auth-context";

export function ChangePasswordPage() {
  const t = useTranslations("auth.passwordChange");
  const { logout, user } = useAuth();
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const minimumLength = user?.is_organization_root ? 12 : 8;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (newPassword.length < minimumLength) return setError(t(user?.is_organization_root ? "passwordTooShortRoot" : "passwordTooShort"));
    if (newPassword !== confirmation) return setError(t("passwordsDoNotMatch"));
    if (newPassword === currentPassword) return setError(t("passwordMustChange"));
    setSubmitting(true);
    setError("");
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword, new_password_confirmation: confirmation });
      logout();
      router.replace("/login?session=password_changed");
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.message.includes("Current password")) setError(t("incorrectCurrentPassword"));
      else setError(t("passwordChangeError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PageFrame section="Administration" title={t("changePassword")}>
      <form onSubmit={(event) => void submit(event)} style={{ display: "grid", gap: 16, maxWidth: 520 }}>
        <label>{t("currentPassword")}<PasswordInput inputStyle={sharedStyles.input} value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /></label>
        <label>{t("newPassword")}<PasswordInput inputStyle={sharedStyles.input} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} minLength={minimumLength} required /></label>
        <label>{t("confirmNewPassword")}<PasswordInput inputStyle={sharedStyles.input} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} minLength={minimumLength} required /></label>
        <div style={{ display: "grid", gap: 6 }} aria-label={t("requirementsTitle")}>
          <strong>{t("requirementsTitle")}</strong>
          <span>{t("minCharacters", { count: minimumLength })}</span>
          <span>{t("requiresUppercase")}</span>
          <span>{t("requiresLowercase")}</span>
          <span>{t("requiresNumber")}</span>
          <span>{t("requiresSpecial")}</span>
        </div>
        {error ? <div style={sharedStyles.error}>{error}</div> : null}
        <button type="submit" style={sharedStyles.button} disabled={submitting}>{submitting ? t("submitting") : t("changePasswordButton")}</button>
      </form>
    </PageFrame>
  );
}
