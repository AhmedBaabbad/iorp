export type InteractionType = "call" | "visit" | "whatsapp" | "email" | "meeting";

export type CustomerInteraction = {
  id: string;
  customer_id: string;
  interaction_type: InteractionType;
  interaction_date: string;
  subject: string;
  summary: string | null;
  outcome: string | null;
  next_step_hint: string | null;
  created_by_user_id: string;
  created_at: string;
};

export type CustomerInteractionCreateRequest = {
  interaction_type: InteractionType;
  interaction_date: string;
  subject: string;
  summary?: string;
  outcome?: string;
  next_step_hint?: string;
};
