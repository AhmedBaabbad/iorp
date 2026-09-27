import type { CreatedBySummary, EligibleSalesOwner, WorkforceSummary } from "./customers";

export type FollowUpStatus = "pending" | "in_progress" | "completed" | "cancelled";
export type FollowUpPriority = "low" | "medium" | "high" | "urgent";

export type FollowUpCustomerSummary = {
  id: string;
  customer_code: string;
  customer_name: string;
};

export type FollowUpAssignedUser = {
  id: string;
  full_name: string;
  email: string;
  workforce: WorkforceSummary | null;
};

export type FollowUp = {
  id: string;
  customer: FollowUpCustomerSummary;
  interaction_id: string | null;
  assigned_user_id: string | null;
  assigned_user: FollowUpAssignedUser | null;
  is_unassigned: boolean;
  created_by: CreatedBySummary | null;
  due_date: string;
  priority: FollowUpPriority;
  status: FollowUpStatus;
  is_overdue: boolean;
  reason: string;
  notes: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type FollowUpListResponse = {
  items: FollowUp[];
  total: number;
  page: number;
  page_size: number;
};

export type FollowUpCreateRequest = {
  reason: string;
  due_date: string;
  priority: FollowUpPriority;
  assigned_user_id?: string | null;
  interaction_id?: string | null;
  notes?: string | null;
};

export type FollowUpUpdateRequest = {
  reason?: string;
  due_date?: string;
  priority?: FollowUpPriority;
  assigned_user_id?: string | null;
  notes?: string | null;
};

export type FollowUpCompleteRequest = {
  completed_at?: string;
  notes?: string;
};

export type EligibleFollowUpAssignee = EligibleSalesOwner;

export type FollowUpListFilters = {
  scope?: "mine" | "all";
  status?: FollowUpStatus;
  priority?: FollowUpPriority;
  customer_id?: string;
  assigned_user_id?: string;
  unassigned?: boolean;
  due_from?: string;
  due_to?: string;
  overdue?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
};

export type FollowUpBulkReassignResponse = {
  from_user_id: string;
  to_user_id: string;
  reassigned_count: number;
};
