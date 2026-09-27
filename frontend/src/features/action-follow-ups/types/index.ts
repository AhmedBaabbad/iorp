export type ActionFollowUpStatus = "on_track" | "delayed" | "blocked" | "completed";

export type ActionFollowUpListItem = {
  id: string;
  corrective_action_id: string;
  follow_up_date: string;
  status: ActionFollowUpStatus;
  progress_note: string;
  next_step: string | null;
  created_by_user_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateActionFollowUpRequest = {
  follow_up_date: string;
  status: ActionFollowUpStatus;
  progress_note: string;
  next_step?: string | null;
};
