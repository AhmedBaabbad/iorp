"use client";

import { useTranslations } from "next-intl";
import type { CSSProperties, FormEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { SectionShell } from "@/components/layout/section-shell";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { usePermission } from "@/features/auth";
import { useFormatter } from "@/hooks/useFormatter";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue, toDatetimeLocalValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type { CustomerInteraction, InteractionType } from "@/types/interactions";
import { createCustomerInteraction, deleteCustomerInteraction, listCustomerInteractions, updateCustomerInteraction } from "./interaction-api";
import { Pagination } from "@/components/pagination/Pagination";
import type { Page } from "@/lib/pagination";

const PAGE_SIZE = 25;
import {
  createDefaultInteractionFormValues,
  toInteractionCreateRequest,
  type InteractionFormValues,
} from "./interaction-form";

type CustomerInteractionsSectionProps = {
  customerId: string;
};

const interactionTypes: InteractionType[] = ["call", "visit", "whatsapp", "email", "meeting"];

const styles: Record<string, CSSProperties> = {
  form: {
    display: "grid",
    gap: "16px",
  },
  formGrid: {
    display: "grid",
    gap: "16px",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  },
  button: {
    ...sharedStyles.button,
    width: "fit-content",
  },
};

export function CustomerInteractionsSection({ customerId }: CustomerInteractionsSectionProps) {
  const t = useTranslations("commercial.interactions");
  const tEnums = useTranslations();
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const fmt = useFormatter();
  const canRead = usePermission("commercial:interactions:read");
  const canCreate = usePermission("commercial:interactions:create");
  // RBAC-002: correcting and removing a recorded interaction are separate permissions.
  const canUpdate = usePermission("commercial:interactions:update");
  const canDelete = usePermission("commercial:interactions:delete");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  // ARCH-PAGE-001: the latest 25 interactions, then older ones page by page.
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<CustomerInteraction> | null>(null);
  const interactions = data?.items ?? [];
  const [values, setValues] = useState<InteractionFormValues>(
    createDefaultInteractionFormValues,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState(false);
  const isMountedRef = useRef(true);

  const loadInteractions = useCallback(async () => {
    if (!isMountedRef.current || !canRead) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await listCustomerInteractions(customerId, page, PAGE_SIZE);
      if (isMountedRef.current) {
        setData(response);
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
  }, [customerId, messages, canRead, page]);

  useEffect(() => {
    isMountedRef.current = true;
    if (canRead) {
      void loadInteractions();
    } else {
      setIsLoading(false);
    }
    return () => {
      isMountedRef.current = false;
    };
  }, [loadInteractions, canRead]);

  function updateField<TField extends keyof InteractionFormValues>(
    field: TField,
    value: InteractionFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setIsSubmitting(true);

    try {
      if (editingId) {
        await updateCustomerInteraction(customerId, editingId, toInteractionCreateRequest(values));
        setEditingId(null);
        setValues(createDefaultInteractionFormValues());
        await loadInteractions();
        return;
      }
      await createCustomerInteraction(customerId, toInteractionCreateRequest(values));
      setValues(createDefaultInteractionFormValues());
      if (page === 1) await loadInteractions(); else setPage(1);  // the new one is on the first page
      setFormSuccess(true);
    } catch (caughtError) {
      setFormError(getApiErrorMessage(caughtError, messages));
    } finally {
      if (isMountedRef.current) {
        setIsSubmitting(false);
      }
    }
  }

  function startEditing(interaction: CustomerInteraction) {
    setEditingId(interaction.id);
    setFormError(null);
    setValues({
      interaction_type: interaction.interaction_type, interaction_date: toDatetimeLocalValue(new Date(interaction.interaction_date)),
      subject: interaction.subject, summary: interaction.summary ?? "", outcome: interaction.outcome ?? "",
      next_step_hint: interaction.next_step_hint ?? "",
    });
  }

  function stopEditing() {
    setEditingId(null);
    setValues(createDefaultInteractionFormValues());
  }

  async function remove(interactionId: string) {
    setBusyId(interactionId);
    setRowError(null);
    try {
      await deleteCustomerInteraction(customerId, interactionId);
      setConfirmingId(null);
      await loadInteractions();
    } catch (caughtError) {
      setRowError(getApiErrorMessage(caughtError, messages));
    } finally {
      setBusyId(null);
    }
  }

  if (!canRead) {
    return null;
  }

  return (
    <>
    {formSuccess ? (
      <SuccessModal
        message={t("createSuccess")}
        okLabel={common("actions.ok")}
        onOk={() => setFormSuccess(false)}
      />
    ) : null}
    <SectionShell
      titleId="interactions-title"
      title={t("sectionTitle")}
      subtitle={t("sectionDescription")}
    >
      {canCreate || editingId ? (
      <form style={styles.form} onSubmit={handleSubmit}>
        {editingId ? <p style={sharedStyles.meta}>{t("editingNotice")}</p> : null}
        <div style={styles.formGrid}>
          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.interactionType")}</span>
            <select
              style={sharedStyles.input}
              value={values.interaction_type}
              onChange={(event) =>
                updateField(
                  "interaction_type",
                  event.target.value as InteractionFormValues["interaction_type"],
                )
              }
              disabled={isSubmitting}
            >
              {interactionTypes.map((type) => (
                <option key={type} value={type}>
                  {getEnumLabel("interaction", "interactionType", type, tEnums)}
                </option>
              ))}
            </select>
          </label>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>
              {t("fields.interactionDate")}{" "}
              <span aria-hidden="true" style={{ color: "var(--danger)" }}>*</span>
            </span>
            <input
              style={sharedStyles.input}
              type="datetime-local"
              value={values.interaction_date}
              onChange={(event) => updateField("interaction_date", event.target.value)}
              disabled={isSubmitting}
              required
            />
          </label>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>
              {t("fields.subject")}{" "}
              <span aria-hidden="true" style={{ color: "var(--danger)" }}>*</span>
            </span>
            <input
              style={sharedStyles.input}
              value={values.subject}
              onChange={(event) => updateField("subject", event.target.value)}
              maxLength={255}
              disabled={isSubmitting}
              required
            />
          </label>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.outcome")}</span>
            <input
              style={sharedStyles.input}
              value={values.outcome}
              onChange={(event) => updateField("outcome", event.target.value)}
              maxLength={255}
              disabled={isSubmitting}
            />
          </label>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>{t("fields.nextStepHint")}</span>
            <input
              style={sharedStyles.input}
              value={values.next_step_hint}
              onChange={(event) => updateField("next_step_hint", event.target.value)}
              maxLength={255}
              disabled={isSubmitting}
            />
          </label>
        </div>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.summary")}</span>
          <textarea
            style={sharedStyles.textarea}
            value={values.summary}
            onChange={(event) => updateField("summary", event.target.value)}
            disabled={isSubmitting}
          />
        </label>

        {formError ? (
          <div style={sharedStyles.error} role="alert">
            {formError}
          </div>
        ) : null}

        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <button style={styles.button} type="submit" disabled={isSubmitting}>
            {isSubmitting ? messages("loading.saving") : editingId ? t("saveChanges") : t("addButton")}
          </button>
          {editingId ? <button type="button" style={sharedStyles.secondaryButton} onClick={stopEditing}>{common("actions.cancel")}</button> : null}
        </div>
      </form>
      ) : null}

      {isLoading && !data ? <div style={sharedStyles.state}>{messages("loading.default")}</div> : null}

      {!isLoading && error ? (
        <div style={sharedStyles.error} role="alert">
          {error}
        </div>
      ) : null}

      {!isLoading && !error && interactions.length === 0 ? (
        <div style={sharedStyles.state}>{t("empty")}</div>
      ) : null}

      {!error && interactions.length > 0 ? (
        <div style={sharedStyles.list}>
          {interactions.map((interaction) => (
            <article key={interaction.id} style={sharedStyles.item}>
              <div style={sharedStyles.itemHeader}>
                <h3 style={sharedStyles.itemTitle}>{interaction.subject}</h3>
                <p style={sharedStyles.meta}>
                  {getEnumLabel("interaction", "interactionType", interaction.interaction_type, tEnums)}
                  {" - "}
                  {fmt.dateTime(interaction.interaction_date)}
                </p>
              </div>
              <p style={sharedStyles.text}>{displayValue(interaction.summary)}</p>
              <p style={sharedStyles.meta}>
                {t("outcomeLabel", {
                  value: interaction.outcome
                    ? getEnumLabel("interaction", "outcome", interaction.outcome, tEnums)
                    : displayValue(null),
                })}
              </p>
              {interaction.next_step_hint ? (
                <p style={sharedStyles.meta}>
                  {t("nextStepLabel", { value: interaction.next_step_hint })}
                </p>
              ) : null}
              <p style={sharedStyles.meta}>
                {t("fields.created")}: {fmt.dateTime(interaction.created_at)}
              </p>
              {canUpdate || canDelete ? (
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                  {canUpdate ? (
                    <button type="button" style={sharedStyles.secondaryButton} disabled={busyId !== null} onClick={() => startEditing(interaction)}>
                      {common("actions.edit")}
                    </button>
                  ) : null}
                  {canDelete && confirmingId !== interaction.id ? (
                    <button type="button" style={sharedStyles.secondaryButton} disabled={busyId !== null} onClick={() => setConfirmingId(interaction.id)}>
                      {common("actions.delete")}
                    </button>
                  ) : null}
                  {canDelete && confirmingId === interaction.id ? (
                    <>
                      <span style={sharedStyles.meta}>{t("deleteConfirm")}</span>
                      <button type="button" style={{ ...sharedStyles.button, background: "var(--danger)", borderColor: "var(--danger)" }}
                        disabled={busyId !== null} onClick={() => void remove(interaction.id)}>{t("deleteYes")}</button>
                      <button type="button" style={sharedStyles.secondaryButton} disabled={busyId !== null} onClick={() => setConfirmingId(null)}>
                        {common("actions.cancel")}
                      </button>
                    </>
                  ) : null}
                </div>
              ) : null}
              {rowError && confirmingId === interaction.id ? <p style={sharedStyles.error} role="alert">{rowError}</p> : null}
            </article>
          ))}
          {data ? <Pagination page={data.page} pageSize={data.page_size} total={data.total} pages={data.pages} disabled={isLoading}
            onPage={setPage} /> : null}
        </div>
      ) : null}
    </SectionShell>
    </>
  );
}
