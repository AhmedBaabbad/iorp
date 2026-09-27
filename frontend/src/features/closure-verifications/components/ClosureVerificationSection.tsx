"use client";

import type { CSSProperties, FormEvent, ReactNode } from "react";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { SectionShell } from "@/components/layout/section-shell";
import { useFormatter } from "@/hooks/useFormatter";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import {
  createClosureVerification,
  getClosureVerification,
} from "../api/closure-verifications-api";
import type {
  ClosureStatus,
  ClosureVerification,
  ClosureVerificationResult,
  CreateClosureVerificationRequest,
} from "../types";
import { ClosureResultBadge } from "./ClosureResultBadge";
import { ClosureStatusBadge } from "./ClosureStatusBadge";

type ClosureVerificationSectionProps = {
  correctiveActionId: string;
  correctiveActionStatus: string;
};

type ClosureVerificationFormValues = {
  verification_date: string;
  verification_result: "" | ClosureVerificationResult;
  closure_status: ClosureStatus;
  notes: string;
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
  actions: {
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
  },
  inlineError: {
    color: "#be123c",
    fontSize: "13px",
    margin: 0,
  },
  detailGrid: {
    display: "grid",
    gap: "1px",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    background: "#e4e7ec",
    borderRadius: "8px",
    overflow: "hidden",
  },
  detailItem: {
    background: "#ffffff",
    padding: "18px",
  },
  detailLabel: {
    color: "#52606d",
    fontSize: "13px",
    fontWeight: 700,
    margin: "0 0 8px",
  },
  detailValue: {
    margin: 0,
    overflowWrap: "anywhere",
  },
  notes: {
    background: "#f8fafc",
    border: "1px solid #e4e7ec",
    borderRadius: "6px",
    lineHeight: 1.55,
    margin: 0,
    padding: "14px",
    whiteSpace: "pre-wrap",
  },
  infoBanner: {
    background: "#fffbeb",
    border: "1px solid #fde68a",
    borderRadius: "6px",
    color: "#92400e",
    lineHeight: 1.5,
    padding: "12px 14px",
  },
};

function createDefaultValues(): ClosureVerificationFormValues {
  return {
    verification_date: new Date().toISOString().slice(0, 10),
    verification_result: "effective",
    closure_status: "closed",
    notes: "",
  };
}

export function ClosureVerificationSection({
  correctiveActionId,
  correctiveActionStatus,
}: ClosureVerificationSectionProps) {
  const t = useTranslations("capa.correctiveActions.closure");
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const [verification, setVerification] = useState<ClosureVerification | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [values, setValues] = useState<ClosureVerificationFormValues>(createDefaultValues);
  const [dateError, setDateError] = useState<string | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);
  const [notesError, setNotesError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let isMounted = true;

    async function loadVerification() {
      try {
        setIsLoading(true);
        setError(null);
        const response = await getClosureVerification(correctiveActionId);

        if (isMounted) {
          setVerification(response);
        }
      } catch (caughtError) {
        if (!isMounted) {
          return;
        }

        if (caughtError instanceof ApiClientError && caughtError.status === 404) {
          setVerification(null);
          return;
        }

        setError(getApiErrorMessage(caughtError, messages));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadVerification();

    return () => {
      isMounted = false;
    };
  }, [correctiveActionId, reloadToken, t]);

  function updateField<TField extends keyof ClosureVerificationFormValues>(
    field: TField,
    value: ClosureVerificationFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
      ...(field === "verification_result"
        ? {
            closure_status:
              value === "not_effective"
                ? "re_opened"
                : current.closure_status === "re_opened"
                  ? "closed"
                  : current.closure_status,
          }
        : {}),
    }));

    if (field === "verification_date") {
      setDateError(null);
    }

    if (field === "verification_result") {
      setResultError(null);
    }

    if (field === "notes") {
      setNotesError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setDateError(null);
    setResultError(null);
    setNotesError(null);

    if (!values.verification_date) {
      setDateError(messages("validation.dateRequired"));
      return;
    }

    if (!values.verification_result) {
      setResultError(messages("validation.resultRequired"));
      return;
    }

    if (!values.notes.trim()) {
      setNotesError(messages("validation.notesRequired"));
      return;
    }

    setIsSubmitting(true);

    try {
      const createdVerification = await createClosureVerification(
        correctiveActionId,
        toCreateRequest(values),
      );
      setVerification(createdVerification);
      setValues(createDefaultValues());
    } catch (caughtError) {
      setFormError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  const canCreateVerification =
    correctiveActionStatus === "in_progress" || correctiveActionStatus === "completed";

  return (
    <SectionShell
      titleId="closure-verification-title"
      title={t("sectionShortTitle")}
      subtitle={t("sectionSubtitle")}
    >
      {isLoading ? <div style={sharedStyles.state}>{t("loading")}</div> : null}

      {!isLoading && error ? (
        <div style={{ display: "grid", gap: "12px" }}>
          <div style={sharedStyles.error} role="alert">
            {error}
          </div>
          <button
            style={{ ...sharedStyles.secondaryButton, width: "fit-content" }}
            type="button"
            onClick={() => setReloadToken((current) => current + 1)}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && verification ? (
        <ClosureVerificationDisplay verification={verification} />
      ) : null}

      {!isLoading && !error && !verification ? (
        <>
          {correctiveActionStatus === "open" ? (
            <div style={sharedStyles.state}>
              {t("noVerificationOpen")}
            </div>
          ) : null}

          {correctiveActionStatus === "closed" ? (
            <div style={sharedStyles.state}>{t("closedWithoutVerification")}</div>
          ) : null}

          {canCreateVerification ? (
            <>
              <div style={sharedStyles.state}>{t("empty")}</div>
              <form style={styles.form} onSubmit={handleSubmit}>
                <div style={styles.formGrid}>
                  <label style={sharedStyles.field}>
                    <span style={sharedStyles.label}>
                      {t("fields.verificationDate")} <span aria-hidden="true" style={{ color: "#be123c" }}>*</span>
                    </span>
                    <input
                      style={sharedStyles.input}
                      type="date"
                      value={values.verification_date}
                      onChange={(event) => updateField("verification_date", event.target.value)}
                      disabled={isSubmitting}
                      required
                    />
                    {dateError ? <p style={styles.inlineError}>{dateError}</p> : null}
                  </label>

                  <label style={sharedStyles.field}>
                    <span style={sharedStyles.label}>
                      {t("fields.verificationResult")} <span aria-hidden="true" style={{ color: "#be123c" }}>*</span>
                    </span>
                    <select
                      style={sharedStyles.input}
                      value={values.verification_result}
                      onChange={(event) =>
                        updateField(
                          "verification_result",
                          event.target.value as ClosureVerificationFormValues["verification_result"],
                        )
                      }
                      disabled={isSubmitting}
                      required
                    >
                      <option value="effective">Effective (Problem fully resolved)</option>
                      <option value="partially_effective">
                        Partially Effective (Issue reduced)
                      </option>
                      <option value="not_effective">Not Effective (Problem persists)</option>
                    </select>
                    {resultError ? <p style={styles.inlineError}>{resultError}</p> : null}
                  </label>

                  <label style={sharedStyles.field}>
                    <span style={sharedStyles.label}>
                      {t("fields.closureStatus")} <span aria-hidden="true" style={{ color: "#be123c" }}>*</span>
                    </span>
                    <select
                      style={sharedStyles.input}
                      value={values.closure_status}
                      onChange={(event) =>
                        updateField("closure_status", event.target.value as ClosureStatus)
                      }
                      disabled={isSubmitting}
                      required
                    >
                      <option value="closed">Closed (Action complete)</option>
                      <option value="re_opened">Re-opened (Requires further action)</option>
                    </select>
                  </label>
                </div>

                <label style={sharedStyles.field}>
                  <span style={sharedStyles.label}>
                    {t("fields.closureNotes")} ({common("labels.required")})
                  </span>
                  <textarea
                    style={{ ...sharedStyles.textarea, minHeight: "120px" }}
                    value={values.notes}
                    onChange={(event) => updateField("notes", event.target.value)}
                    disabled={isSubmitting}
                    placeholder="Document the verification findings and evidence..."
                    required
                  />
                  {notesError ? <p style={styles.inlineError}>{notesError}</p> : null}
                </label>

                <div style={sharedStyles.state}>{t("verifiedByCurrentUser")}</div>

                {formError ? (
                  <div style={sharedStyles.error} role="alert">
                    {formError}
                  </div>
                ) : null}

                <div style={styles.actions}>
                  <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
                    {isSubmitting ? t("saving") : t("recordButton")}
                  </button>
                </div>
              </form>
            </>
          ) : null}
        </>
      ) : null}
    </SectionShell>
  );
}

function ClosureVerificationDisplay({
  verification,
}: {
  verification: ClosureVerification;
}) {
  const t = useTranslations("capa.correctiveActions.closure");
  const fmt = useFormatter();

  return (
    <>
      {verification.verification_result === "not_effective" ? (
        <div style={styles.infoBanner}>
          {t("notEffectiveBanner")}
        </div>
      ) : null}

      <section style={styles.detailGrid} aria-label={t("sectionShortTitle")}>
        <DetailItem label={t("fields.verificationDate")} value={fmt.date(verification.verification_date)} />
        <DetailItem
          label={t("fields.verificationResult")}
          value={<ClosureResultBadge result={verification.verification_result} />}
        />
        <DetailItem
          label={t("fields.closureStatus")}
          value={<ClosureStatusBadge status={verification.closure_status} />}
        />
        <DetailItem label={t("fields.verifiedBy")} value={verifiedBy(verification, t)} />
      </section>

      <section>
        <h3 style={{ margin: "0 0 10px", fontSize: "16px" }}>{t("fields.closureNotes")}</h3>
        <p style={styles.notes}>{verification.notes}</p>
      </section>
    </>
  );
}

function DetailItem({
  label,
  value,
}: {
  label: string;
  value: string | number | null | ReactNode;
}) {
  return (
    <div style={styles.detailItem}>
      <p style={styles.detailLabel}>{label}</p>
      <p style={styles.detailValue}>
        {typeof value === "string" || typeof value === "number" || value === null
          ? displayValue(value)
          : value}
      </p>
    </div>
  );
}

function toCreateRequest(
  values: ClosureVerificationFormValues,
): CreateClosureVerificationRequest {
  return {
    verification_date: values.verification_date,
    verification_result: values.verification_result || "effective",
    closure_status: values.closure_status,
    notes: values.notes.trim(),
  };
}

function verifiedBy(verification: ClosureVerification, t: (key: string) => string) {
  return verification.verified_by_user_id ?? verification.verified_by ?? t("currentUser");
}
