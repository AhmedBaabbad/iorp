"use client";

import type { CSSProperties, FormEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { SectionShell } from "@/components/layout/section-shell";
import { useAuth } from "@/features/auth";
import { getErrorMessage } from "@/lib/errors";
import { displayValue, formatDate } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type { FollowUpListItem } from "@/types/followups";
import {
  completeFollowUp,
  createCustomerFollowUp,
  listCustomerFollowUps,
} from "./followup-api";
import {
  createDefaultFollowUpFormValues,
  toFollowUpCreateRequest,
  type FollowUpFormValues,
} from "./followup-form";

type CustomerFollowUpsSectionProps = {
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
  compactButton: {
    ...sharedStyles.secondaryButton,
    minHeight: "36px",
    padding: "8px 12px",
  },
};

export function CustomerFollowUpsSection({ customerId }: CustomerFollowUpsSectionProps) {
  const { user } = useAuth();
  const [followUps, setFollowUps] = useState<FollowUpListItem[]>([]);
  const [values, setValues] = useState<FollowUpFormValues>(createDefaultFollowUpFormValues);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [completingId, setCompletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadFollowUps = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await listCustomerFollowUps(customerId);
      if (isMountedRef.current) {
        setFollowUps(response);
      }
    } catch (caughtError) {
      if (isMountedRef.current) {
        setError(getErrorMessage(caughtError, "Unable to load follow-ups."));
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [customerId]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadFollowUps();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadFollowUps]);

  function updateField<TField extends keyof FollowUpFormValues>(
    field: TField,
    value: FollowUpFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (!user) {
      setFormError("Unable to assign follow-up without a signed-in user.");
      return;
    }

    setIsSubmitting(true);

    try {
      await createCustomerFollowUp(customerId, toFollowUpCreateRequest(values, user.id));
      setValues(createDefaultFollowUpFormValues());
      await loadFollowUps();
    } catch (caughtError) {
      setFormError(getErrorMessage(caughtError, "Unable to create follow-up."));
    } finally {
      if (isMountedRef.current) {
        setIsSubmitting(false);
      }
    }
  }

  async function handleComplete(followUpId: string) {
    setCompletingId(followUpId);
    setError(null);

    try {
      await completeFollowUp(followUpId);
      await loadFollowUps();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to complete follow-up."));
    } finally {
      if (isMountedRef.current) {
        setCompletingId(null);
      }
    }
  }

  return (
    <SectionShell
      titleId="follow-ups-title"
      title="Follow-ups"
      subtitle="Create next actions and complete pending follow-ups."
    >
        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={styles.formGrid}>
            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Due date <span aria-hidden="true" style={{ color: "#be123c" }}>*</span></span>
              <input
                style={sharedStyles.input}
                type="datetime-local"
                value={values.due_date}
                onChange={(event) => updateField("due_date", event.target.value)}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Priority</span>
              <select
                style={sharedStyles.input}
                value={values.priority}
                onChange={(event) =>
                  updateField("priority", event.target.value as FollowUpFormValues["priority"])
                }
                disabled={isSubmitting}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Reason <span aria-hidden="true" style={{ color: "#be123c" }}>*</span></span>
              <input
                style={sharedStyles.input}
                value={values.reason}
                onChange={(event) => updateField("reason", event.target.value)}
                maxLength={255}
                disabled={isSubmitting}
                required
              />
            </label>
          </div>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>Notes</span>
            <textarea
              style={sharedStyles.textarea}
              value={values.notes}
              onChange={(event) => updateField("notes", event.target.value)}
              disabled={isSubmitting}
            />
          </label>

          {user ? (
            <p style={{ ...sharedStyles.meta, marginTop: "4px" }}>
              Assigned to: {user.full_name}
            </p>
          ) : null}

          {formError ? (
            <div style={sharedStyles.error} role="alert">
              {formError}
            </div>
          ) : null}

          <button style={styles.button} type="submit" disabled={isSubmitting || !user}>
            {isSubmitting ? "Saving…" : "Add follow-up"}
          </button>
        </form>

        {isLoading ? <div style={sharedStyles.state}>Loading follow-ups...</div> : null}

        {!isLoading && error ? (
          <div style={sharedStyles.error} role="alert">
            {error}
          </div>
        ) : null}

        {!isLoading && !error && followUps.length === 0 ? (
          <div style={sharedStyles.state}>No follow-ups recorded yet.</div>
        ) : null}

        {!isLoading && !error && followUps.length > 0 ? (
          <div style={sharedStyles.list}>
            {followUps.map((followUp) => (
              <article key={followUp.id} style={sharedStyles.item}>
                <div style={sharedStyles.itemHeader}>
                  <div>
                    <h3 style={sharedStyles.itemTitle}>{followUp.reason}</h3>
                    <p style={sharedStyles.meta}>
                      Due {formatDate(followUp.due_date)} · {followUp.priority}
                    </p>
                  </div>
                  <span style={statusBadgeStyle(followUp.status)}>{followUp.status}</span>
                </div>

                <p style={sharedStyles.text}>Notes: {displayValue(followUp.notes)}</p>
                <p style={sharedStyles.meta}>
                  Completed:{" "}
                  {followUp.completed_at ? formatDate(followUp.completed_at) : "-"}
                </p>

                {followUp.status === "pending" ? (
                  <button
                    style={{ ...styles.compactButton, marginTop: "12px" }}
                    type="button"
                    disabled={completingId === followUp.id}
                    onClick={() => void handleComplete(followUp.id)}
                  >
                    {completingId === followUp.id ? "Completing..." : "Mark completed"}
                  </button>
                ) : null}
              </article>
            ))}
          </div>
        ) : null}
    </SectionShell>
  );
}

function statusBadgeStyle(status: FollowUpListItem["status"]) {
  const colors = {
    pending: { background: "#fef3c7", color: "#92400e" },
    completed: { background: "#dcfce7", color: "#166534" },
    cancelled: { background: "#f3f4f6", color: "#4b5563" },
  };

  return {
    ...sharedStyles.badge,
    ...colors[status],
  };
}
