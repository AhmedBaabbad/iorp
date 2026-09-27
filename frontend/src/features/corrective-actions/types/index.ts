export type CorrectiveActionStatus = "open" | "in_progress" | "completed" | "closed";

export type CorrectiveActionPriority = "urgent" | "high" | "normal" | "low";

export type CorrectiveActionType =
  | "corrective"
  | "preventive"
  | "improvement"
  | "containment";

export type CorrectiveActionSourceType =
  | "quality_rejection"
  | "ncr_report"
  | "quality_defect"
  | "ncr_item"
  | "manual";

export type CorrectiveActionListFilters = {
  action_type?: CorrectiveActionType;
  status?: CorrectiveActionStatus;
  priority?: CorrectiveActionPriority;
  source_type?: CorrectiveActionSourceType;
};

export type CorrectiveActionListItem = {
  id: string;
  action_code: string;
  title: string;
  action_type: CorrectiveActionType;
  priority: CorrectiveActionPriority;
  status: CorrectiveActionStatus;
  due_date: string;
  owner_user_id: string;
  source_type: CorrectiveActionSourceType | null;
  source_id: string | null;
  created_at: string;
  updated_at: string;
};

export type CorrectiveActionDetail = CorrectiveActionListItem & {
  description: string;
  notes: string | null;
};

export type CreateCorrectiveActionRequest = {
  title: string;
  description: string;
  action_type: CorrectiveActionType;
  priority: CorrectiveActionPriority;
  due_date: string;
  owner_user_id: string;
  source_type?: CorrectiveActionSourceType | null;
  source_id?: string | null;
  notes?: string | null;
};

export type UpdateCorrectiveActionStatusRequest = {
  status: CorrectiveActionStatus;
};
