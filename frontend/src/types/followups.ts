import type { PriorityLevel } from "./customers";

export type FollowUpStatus = "pending" | "completed" | "cancelled";

export type FollowUpListItem = {
  id: string;
  customer_id: string;
  interaction_id?: string | null;
  assigned_user_id: string;
  due_date: string;
  priority: PriorityLevel;
  status: FollowUpStatus;
  reason: string;
  notes?: string | null;
  completed_at: string | null;
  created_at: string;
};

export type FollowUpCreateRequest = {
  interaction_id?: string | null;
  assigned_user_id: string;
  due_date: string;
  priority: PriorityLevel;
  reason: string;
  notes?: string;
};

export type FollowUpCompleteRequest = {
  completed_at?: string;
  notes?: string;
};
