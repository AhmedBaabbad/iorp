"use client";

import { useTranslations } from "next-intl";
import type { CSSProperties, FormEvent } from "react";
import { useState } from "react";

import { SuccessModal } from "@/components/ui/SuccessModal";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText, toDatetimeLocalValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { createSampleEvaluation } from "../api/sample-evaluations-api";
import type {
  CreateSampleEvaluationRequest,
  SampleEvaluationNextAction,
  SampleEvaluationResultStatus,
} from "../types";

type SampleEvaluationFormProps = {
  sampleId: string;
  onCreated: () => void | Promise<void>;
};

type SampleEvaluationFormValues = {
  evaluation_date: string;
  result_status: SampleEvaluationResultStatus;
  next_action: SampleEvaluationNextAction;
  comments: string;
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

function createDefaultValues(): SampleEvaluationFormValues {
  return {
    evaluation_date: toDatetimeLocalValue(new Date()),
    result_status: "accepted",
    next_action: "proceed_to_quote",
    comments: "",
  };
}

export function SampleEvaluationForm({
  sampleId,
  onCreated,
}: SampleEvaluationFormProps) {
  const messages = useTranslations("messages");
  const tEnums = useTranslations();
  const t = useTranslations("commercial.samples.evaluations");
  const common = useTranslations("common");
  const [values, setValues] = useState<SampleEvaluationFormValues>(createDefaultValues);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState(false);

  function updateField<TField extends keyof SampleEvaluationFormValues>(
    field: TField,
    value: SampleEvaluationFormValues[TField],
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
      await createSampleEvaluation(sampleId, toCreateRequest(values));
      setValues(createDefaultValues());
      setFormSuccess(true);
    } catch (caughtError) {
      setFormError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
    {formSuccess ? (
      <SuccessModal
        message={t("createSuccess")}
        okLabel={common("actions.ok")}
        onOk={() => { setFormSuccess(false); void onCreated(); }}
      />
    ) : null}
    <form style={styles.form} onSubmit={handleSubmit}>
      <div style={styles.formGrid}>
        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>
            {t("fields.evaluationDate")} <span aria-hidden="true" style={{ color: "#be123c" }}>*</span>
          </span>
          <input
            style={sharedStyles.input}
            type="datetime-local"
            value={values.evaluation_date}
            onChange={(event) => updateField("evaluation_date", event.target.value)}
            disabled={isSubmitting}
            required
          />
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.resultStatus")}</span>
          <select
            style={sharedStyles.input}
            value={values.result_status}
            onChange={(event) =>
              updateField(
                "result_status",
                event.target.value as SampleEvaluationResultStatus,
              )
            }
            disabled={isSubmitting}
            required
          >
            <option value="accepted">
              {getEnumLabel("sampleEvaluation", "resultStatus", "accepted", tEnums)}
            </option>
            <option value="rejected">
              {getEnumLabel("sampleEvaluation", "resultStatus", "rejected", tEnums)}
            </option>
            <option value="needs_modification">
              {getEnumLabel("sampleEvaluation", "resultStatus", "needs_modification", tEnums)}
            </option>
          </select>
        </label>

        <label style={sharedStyles.field}>
          <span style={sharedStyles.label}>{t("fields.nextAction")}</span>
          <select
            style={sharedStyles.input}
            value={values.next_action}
            onChange={(event) =>
              updateField("next_action", event.target.value as SampleEvaluationNextAction)
            }
            disabled={isSubmitting}
            required
          >
            <option value="proceed_to_quote">
              {getEnumLabel("sampleEvaluation", "nextAction", "proceed_to_quote", tEnums)}
            </option>
            <option value="revise_sample">
              {getEnumLabel("sampleEvaluation", "nextAction", "revise_sample", tEnums)}
            </option>
            <option value="close_request">
              {getEnumLabel("sampleEvaluation", "nextAction", "close_request", tEnums)}
            </option>
            <option value="further_review">
              {getEnumLabel("sampleEvaluation", "nextAction", "further_review", tEnums)}
            </option>
          </select>
        </label>
      </div>

      <label style={sharedStyles.field}>
        <span style={sharedStyles.label}>{t("fields.comments")}</span>
        <textarea
          style={sharedStyles.textarea}
          value={values.comments}
          onChange={(event) => updateField("comments", event.target.value)}
          disabled={isSubmitting}
          required
        />
      </label>

      {formError ? (
        <div style={sharedStyles.error} role="alert">
          {formError}
        </div>
      ) : null}

      <button style={styles.button} type="submit" disabled={isSubmitting}>
        {isSubmitting ? t("saving") : t("addButton")}
      </button>
    </form>
    </>
  );
}

function toCreateRequest(
  values: SampleEvaluationFormValues,
): CreateSampleEvaluationRequest {
  return {
    evaluation_date: new Date(values.evaluation_date).toISOString(),
    result_status: values.result_status,
    next_action: values.next_action,
    comments: optionalText(values.comments),
  };
}
