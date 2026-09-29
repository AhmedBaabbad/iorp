"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { FormEvent } from "react";
import { useCallback, useEffect, useState } from "react";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { PasswordInput } from "@/components/PasswordInput";
import { ApiClientError } from "@/lib/api-client";
import type { PlatformAdministrator, PlatformAdministratorCreate } from "@/types/platform";
import {
  createPlatformAdministrator,
  deactivatePlatformAdministrator,
  listPlatformAdministrators,
  resetPlatformAdministratorPassword,
  updatePlatformAdministrator,
} from "./platform-api";
import { usePlatformAuth } from "./platform-auth-context";
import { PlatformProtectedRoute } from "./platform-protected-route";
import { platformStyles as styles } from "./platform-styles";

const emptyForm: PlatformAdministratorCreate = {
  full_name: "", email: "", role: "admin", password: "", password_confirmation: "",
};

function PlatformAdministratorsContent() {
  const t = useTranslations("platform.administrators");
  const { account, token } = usePlatformAuth();
  const [items, setItems] = useState<PlatformAdministrator[] | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [resetTarget, setResetTarget] = useState<PlatformAdministrator | null>(null);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");

  const load = useCallback(() => {
    listPlatformAdministrators(token).then(setItems).catch(() => setError(t("loadError")));
  }, [t, token]);
  useEffect(() => { load(); }, [load]);

  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (form.password !== form.password_confirmation) return setError(t("errors.passwordMismatch"));
    setBusy(true); setError("");
    try {
      await createPlatformAdministrator(form, token);
      setForm(emptyForm); setShowCreate(false); setSuccess(t("created")); load();
    } catch (caught) {
      setError(caught instanceof ApiClientError ? caught.message : t("errors.generic"));
    } finally { setBusy(false); }
  }

  async function toggleRole(item: PlatformAdministrator) {
    setBusy(true); setError("");
    try {
      await updatePlatformAdministrator(item.id, { role: item.role === "root" ? "admin" : "root" }, token);
      setSuccess(t("updated")); load();
    } catch (caught) { setError(caught instanceof ApiClientError ? caught.message : t("errors.generic")); }
    finally { setBusy(false); }
  }

  async function deactivate(item: PlatformAdministrator) {
    if (!window.confirm(t("confirmDeactivate", { name: item.full_name }))) return;
    setBusy(true); setError("");
    try { await deactivatePlatformAdministrator(item.id, token); setSuccess(t("deactivated")); load(); }
    catch (caught) { setError(caught instanceof ApiClientError ? caught.message : t("errors.generic")); }
    finally { setBusy(false); }
  }

  async function submitReset(event: FormEvent) {
    event.preventDefault();
    if (!resetTarget) return;
    if (password !== confirmation) return setError(t("errors.passwordMismatch"));
    setBusy(true); setError("");
    try {
      await resetPlatformAdministratorPassword(resetTarget.id, { new_password: password, new_password_confirmation: confirmation }, token);
      setResetTarget(null); setPassword(""); setConfirmation(""); setSuccess(t("passwordReset"));
    } catch (caught) { setError(caught instanceof ApiClientError ? caught.message : t("errors.generic")); }
    finally { setBusy(false); }
  }

  if (!account?.is_root) return <main style={styles.page}><div style={styles.error}>{t("accessDenied")}</div></main>;

  return (
    <main style={styles.page}>
      <header style={{ maxWidth: 980, margin: "0 auto 24px", display: "flex", justifyContent: "space-between", gap: 16 }}>
        <div><p style={styles.eyebrow}>{t("eyebrow")}</p><h1 style={styles.title}>{t("title")}</h1><p style={{ color: "var(--text-subtle)" }}>{t("subtitle")}</p></div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}><LanguageSwitcher label={t("languageLabel")} /><Link href="/platform/dashboard" style={styles.secondaryButton}>{t("back")}</Link></div>
      </header>
      <section style={{ maxWidth: 980, margin: "0 auto" }}>
        {error && <div role="alert" style={{ ...styles.error, marginBottom: 12 }}>{error}</div>}
        {success && <div style={{ ...styles.success, marginBottom: 12 }}>{success}</div>}
        <button type="button" style={styles.button} onClick={() => setShowCreate((v) => !v)}>{showCreate ? t("cancel") : t("newAdmin")}</button>
        {showCreate && <form onSubmit={submitCreate} style={{ ...styles.panel, display: "grid", gap: 14, marginTop: 14, padding: 24 }}>
          <label style={styles.field}><span style={styles.label}>{t("fields.fullName")}</span><input style={styles.input} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required /></label>
          <label style={styles.field}><span style={styles.label}>{t("fields.email")}</span><input style={styles.input} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></label>
          <label style={styles.field}><span style={styles.label}>{t("fields.role")}</span><select style={styles.input} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as "root" | "admin" })}><option value="admin">{t("roles.admin")}</option><option value="root">{t("roles.root")}</option></select></label>
          <label style={styles.field}><span style={styles.label}>{t("fields.password")}</span><PasswordInput inputStyle={styles.input} minLength={12} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required /></label>
          <label style={styles.field}><span style={styles.label}>{t("fields.confirmPassword")}</span><PasswordInput inputStyle={styles.input} minLength={12} value={form.password_confirmation} onChange={(e) => setForm({ ...form, password_confirmation: e.target.value })} required /></label>
          <button style={styles.button} disabled={busy}>{busy ? t("saving") : t("create")}</button>
        </form>}
        <div style={{ ...styles.panel, padding: 0, overflowX: "auto", marginTop: 16 }}>
          {items === null ? <p style={{ padding: 20 }}>{t("loading")}</p> : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr>{["name", "email", "role", "status", "lastLogin", "actions"].map((key) => <th key={key} style={{ padding: 12, textAlign: "start" }}>{t(`table.${key}`)}</th>)}</tr></thead>
              <tbody>{items.map((item) => <tr key={item.id} style={{ borderTop: "1px solid var(--border-strong)" }}>
                <td style={{ padding: 12 }}>{item.full_name}{item.is_bootstrap_root ? <div style={{ color: "var(--accent-strong)", fontSize: 12 }}>{t("bootstrapProtected")}</div> : null}</td>
                <td style={{ padding: 12 }}>{item.email}</td>
                <td style={{ padding: 12 }}><span style={{ ...(item.role === "root" ? styles.badgeRoot : styles.badgeAdmin) }}>{t(`roles.${item.role}`)}</span></td>
                <td style={{ padding: 12 }}><span style={item.status === "active" ? styles.badgeActive : styles.badgeInactive}>{t(`statuses.${item.status}`)}</span></td>
                <td style={{ padding: 12 }}>{item.last_login_at ? new Date(item.last_login_at).toLocaleString() : t("notAvailable")}</td>
                <td style={{ padding: 12 }}><div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}><button style={styles.secondaryButton} disabled={busy || item.is_bootstrap_root} onClick={() => void toggleRole(item)}>{item.role === "root" ? t("actions.demote") : t("actions.promote")}</button><button style={styles.secondaryButton} disabled={busy} onClick={() => setResetTarget(item)}>{t("actions.resetPassword")}</button><button style={styles.dangerButton} disabled={busy || item.status === "inactive" || item.is_bootstrap_root} onClick={() => void deactivate(item)}>{t("actions.deactivate")}</button></div></td>
              </tr>)}</tbody>
            </table>
          )}
        </div>
      </section>
      {resetTarget && <div style={{ position: "fixed", inset: 0, display: "grid", placeItems: "center", background: "var(--overlay)", padding: 20 }}><form onSubmit={submitReset} style={{ ...styles.panel, width: "min(460px, 100%)", padding: 24 }}><h2>{t("resetTitle", { name: resetTarget.full_name })}</h2><label style={styles.field}><span style={styles.label}>{t("fields.password")}</span><PasswordInput inputStyle={styles.input} minLength={12} value={password} onChange={(e) => setPassword(e.target.value)} required /></label><label style={styles.field}><span style={styles.label}>{t("fields.confirmPassword")}</span><PasswordInput inputStyle={styles.input} minLength={12} value={confirmation} onChange={(e) => setConfirmation(e.target.value)} required /></label><div style={{ display: "flex", gap: 8, marginTop: 16 }}><button style={styles.dangerButton} disabled={busy}>{t("actions.resetPassword")}</button><button type="button" style={styles.secondaryButton} onClick={() => setResetTarget(null)}>{t("cancel")}</button></div></form></div>}
    </main>
  );
}

export function PlatformAdministratorsPage() {
  return <PlatformProtectedRoute><PlatformAdministratorsContent /></PlatformProtectedRoute>;
}
