"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { createAdminRole, getAdminRole, updateAdminRole } from "../api/admin-roles-api";

type Props = { roleId?: string };

export function AdminRoleForm({ roleId }: Props) {
  const router = useRouter();
  const t = useTranslations("administration.roles");
  const messages = useTranslations("messages");
  const isEdit = Boolean(roleId);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(isEdit);
  const [isEditable, setIsEditable] = useState(true);

  useEffect(() => {
    if (!roleId) return;
    getAdminRole(roleId)
      .then((role) => { setName(role.name); setCode(role.code); setDescription(role.description ?? ""); setIsEditable(role.is_editable); })
      .catch((caughtError) => setError(getApiErrorMessage(caughtError, messages)))
      .finally(() => setIsLoading(false));
  }, [messages, roleId]);

  async function submit() {
    setError(null);
    try {
      if (isEdit && roleId) {
        await updateAdminRole(roleId, { name, code, description: description || null });
        router.push(`/admin/roles/${roleId}`);
      } else {
        const role = await createAdminRole({ name, code, description: description || undefined });
        router.push(`/admin/roles/${role.id}`);
      }
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    }
  }

  if (isLoading) {
    return (
      <PageFrame section="Administration" title={t("editTitle")}>
        <div style={sharedStyles.state}>{t("loadingDetail")}</div>
      </PageFrame>
    );
  }

  return (
    <PageFrame
      section={t("section")}
      title={isEdit ? t("editTitle") : t("createTitle")}
      subtitle={isEdit ? t("editSubtitle") : t("createSubtitle")}
    >
      {error ? <div style={sharedStyles.error}>{error}</div> : null}
      {!isEditable ? <div style={sharedStyles.error}>{t("systemEditBlocked")}</div> : null}
      <form onSubmit={(e) => { e.preventDefault(); void submit(); }} style={{ display: "grid", gap: "16px", maxWidth: "520px" }}>
        <input disabled={!isEditable} style={sharedStyles.input} value={name} onChange={(e) => setName(e.target.value)} placeholder={t("fields.name")} required />
        <input disabled={!isEditable} style={sharedStyles.input} value={code} onChange={(e) => setCode(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"))} placeholder={t("fields.code")} required />
        <small>{!isEditable ? t("codeImmutableHint") : t("codeFormatHint")}</small>
        <textarea disabled={!isEditable} style={sharedStyles.textarea} value={description} onChange={(e) => setDescription(e.target.value)} placeholder={t("fields.description")} />
        {isEditable ? <button style={sharedStyles.button} type="submit">{isEdit ? t("updateButton") : t("createButton")}</button> : null}
      </form>
    </PageFrame>
  );
}
