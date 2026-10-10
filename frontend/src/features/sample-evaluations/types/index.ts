export type SampleEvaluationResultStatus =
  | "accepted"
  | "rejected"
  | "needs_modification";

export type SampleEvaluationNextAction =
  | "proceed_to_quote"
  | "revise_sample"
  | "close_request"
  | "further_review";

export type SampleEvaluationListItem = {
  id: string;
  sample_id: string;
  evaluation_date: string;
  result_status: SampleEvaluationResultStatus;
  comments: string | null;
  next_action: SampleEvaluationNextAction;
  evaluated_by_user_id: string;
  evaluated_by_name: string | null;
  created_at: string;
};

export type CreateSampleEvaluationRequest = {
  evaluation_date: string;
  result_status: SampleEvaluationResultStatus;
  comments?: string | null;
  next_action: SampleEvaluationNextAction;
};
