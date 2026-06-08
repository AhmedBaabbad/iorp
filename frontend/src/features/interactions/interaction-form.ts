import { optionalText, toDatetimeLocalValue } from "@/lib/utils";
import type {
  CustomerInteractionCreateRequest,
  InteractionType,
} from "@/types/interactions";

export type InteractionFormValues = {
  interaction_type: InteractionType;
  interaction_date: string;
  subject: string;
  summary: string;
  outcome: string;
  next_step_hint: string;
};

export function createDefaultInteractionFormValues(): InteractionFormValues {
  return {
    interaction_type: "call",
    interaction_date: toDatetimeLocalValue(new Date()),
    subject: "",
    summary: "",
    outcome: "",
    next_step_hint: "",
  };
}

export function toInteractionCreateRequest(
  values: InteractionFormValues,
): CustomerInteractionCreateRequest {
  return {
    interaction_type: values.interaction_type,
    interaction_date: new Date(values.interaction_date).toISOString(),
    subject: values.subject.trim(),
    summary: optionalText(values.summary),
    outcome: optionalText(values.outcome),
    next_step_hint: optionalText(values.next_step_hint),
  };
}
