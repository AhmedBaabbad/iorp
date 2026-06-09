"use client";

import type { CSSProperties, FormEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { SectionShell } from "@/components/layout/section-shell";
import { getErrorMessage } from "@/lib/errors";
import { displayValue, formatDate } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type { CustomerInteraction } from "@/types/interactions";
import { createCustomerInteraction, listCustomerInteractions } from "./interaction-api";
import {
  createDefaultInteractionFormValues,
  toInteractionCreateRequest,
  type InteractionFormValues,
} from "./interaction-form";

type CustomerInteractionsSectionProps = {
  customerId: string;
};

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
  const [interactions, setInteractions] = useState<CustomerInteraction[]>([]);
  const [values, setValues] = useState<InteractionFormValues>(
    createDefaultInteractionFormValues,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadInteractions = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await listCustomerInteractions(customerId);
      if (isMountedRef.current) {
        setInteractions(response);
      }
    } catch (caughtError) {
      if (isMountedRef.current) {
        setError(getErrorMessage(caughtError, "Unable to load interactions."));
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [customerId]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadInteractions();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadInteractions]);

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
      await createCustomerInteraction(customerId, toInteractionCreateRequest(values));
      setValues(createDefaultInteractionFormValues());
      await loadInteractions();
    } catch (caughtError) {
      setFormError(getErrorMessage(caughtError, "Unable to create interaction."));
    } finally {
      if (isMountedRef.current) {
        setIsSubmitting(false);
      }
    }
  }

  return (
    <SectionShell
      titleId="interactions-title"
      title="Interactions"
      subtitle="Record calls, visits, messages, and meetings."
    >
        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={styles.formGrid}>
            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Type</span>
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
                <option value="call">Call</option>
                <option value="visit">Visit</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="email">Email</option>
                <option value="meeting">Meeting</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Date <span aria-hidden="true" style={{ color: "#be123c" }}>*</span></span>
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
              <span style={sharedStyles.label}>Subject <span aria-hidden="true" style={{ color: "#be123c" }}>*</span></span>
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
              <span style={sharedStyles.label}>Outcome</span>
              <input
                style={sharedStyles.input}
                value={values.outcome}
                onChange={(event) => updateField("outcome", event.target.value)}
                maxLength={255}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Next step hint</span>
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
            <span style={sharedStyles.label}>Summary</span>
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

          <button style={styles.button} type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Add interaction"}
          </button>
        </form>

        {isLoading ? <div style={sharedStyles.state}>Loading interactions...</div> : null}

        {!isLoading && error ? (
          <div style={sharedStyles.error} role="alert">
            {error}
          </div>
        ) : null}

        {!isLoading && !error && interactions.length === 0 ? (
          <div style={sharedStyles.state}>No interactions recorded yet.</div>
        ) : null}

        {!isLoading && !error && interactions.length > 0 ? (
          <div style={sharedStyles.list}>
            {interactions.map((interaction) => (
              <article key={interaction.id} style={sharedStyles.item}>
                <div style={sharedStyles.itemHeader}>
                  <h3 style={sharedStyles.itemTitle}>{interaction.subject}</h3>
                  <p style={sharedStyles.meta}>
                    {interaction.interaction_type} · {formatDate(interaction.interaction_date)}
                  </p>
                </div>
                <p style={sharedStyles.text}>{displayValue(interaction.summary)}</p>
                <p style={sharedStyles.meta}>Outcome: {displayValue(interaction.outcome)}</p>
                {interaction.next_step_hint ? (
                  <p style={sharedStyles.meta}>Next step: {interaction.next_step_hint}</p>
                ) : null}
              </article>
            ))}
          </div>
        ) : null}
    </SectionShell>
  );
}
