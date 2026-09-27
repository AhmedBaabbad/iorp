"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties, FormEvent } from "react";
import { useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { createRole, updateRole } from "../api/roles-api";
import type { RoleDetail } from "../types";

const styles: Record<string, CSSProperties> = {
  card: { background: "#ffffff", border: "1px solid #d9dee7", borderRadius: "8px", padding: "28px", maxWidth: "600px" },
  field: { display: "grid", gap: "6px", marginBottom: "18px" },
  label: { fontSize: "14px", fontWeight: 600, color: "#1f2933" },
  actions: { display: "flex", gap: "12px", marginTop: "24px" },
};

type RoleFormProps = {
  role?: RoleDetail;
};

export function RoleForm({ role }: RoleFormProps) {
  const t = useTranslations("administration.roles");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const router = useRouter();
  const isEdit = Boolean(role);

  const [name, setName] = useState(role?.name ?? "");
  const [code, setCode] = useState(role?.code ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      if (isEdit && role) {
        await updateRole(role.id, { name: name || undefined, description: description || null });
      } else {
        await createRole({ name, code, description: description || null });
      }
      router.push("/roles");
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <PageFrame
      section="Administration"
      title={isEdit ? t("editTitle") : t("createTitle")}
      subtitle={isEdit ? t("editSubtitle") : t("createSubtitle")}
    >
      <div style={styles.card}>
        <form onSubmit={(e) => void handleSubmit(e)}>
          <div style={styles.field}>
            <label htmlFor="name" style={styles.label}>{t("fields.name")}</label>
            <input id="name" style={sharedStyles.input} value={name} onChange={(e) => setName(e.target.value)} required minLength={1} maxLength={120} />
          </div>
          {!isEdit ? (
            <div style={styles.field}>
              <label htmlFor="code" style={styles.label}>{t("fields.code")}</label>
              <input id="code" style={sharedStyles.input} value={code} onChange={(e) => setCode(e.target.value)} required minLength={1} maxLength={64} />
            </div>
          ) : null}
          <div style={styles.field}>
            <label htmlFor="description" style={styles.label}>{t("fields.description")}</label>
            <textarea id="description" style={{ ...sharedStyles.input, minHeight: "80px" }} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          {error ? <div style={sharedStyles.error} role="alert">{error}</div> : null}
          <div style={styles.actions}>
            <button type="submit" style={sharedStyles.button} disabled={isSubmitting}>
              {isSubmitting ? messages("loading.saving") : (isEdit ? t("updateButton") : t("createButton"))}
            </button>
            <button type="button" style={sharedStyles.secondaryButton} onClick={() => router.back()}>{common("actions.cancel")}</button>
          </div>
        </form>
      </div>
    </PageFrame>
  );
}
