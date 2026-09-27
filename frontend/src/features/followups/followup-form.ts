import { optionalText, toDatetimeLocalValue } from "@/lib/utils";
import type { FollowUpCreateRequest, FollowUpPriority } from "@/types/followups";

export type FollowUpFormValues = {
  due_date: string;
  priority: FollowUpPriority;
  reason: string;
  notes: string;
  assigned_user_id: string;
};

export function createDefaultFollowUpFormValues(): FollowUpFormValues {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);

  return {
    due_date: toDatetimeLocalValue(tomorrow),
    priority: "medium",
    reason: "",
    notes: "",
    assigned_user_id: "",
  };
}

/**
 * `includeAssignee` controls whether assigned_user_id is sent at all:
 * eligible-without-assign callers must omit the field entirely (not send
 * null/empty) so the backend never sees an attempted self-assignment change.
 */
export function toFollowUpCreateRequest(
  values: FollowUpFormValues,
  includeAssignee: boolean,
): FollowUpCreateRequest {
  return {
    reason: values.reason.trim(),
    due_date: new Date(values.due_date).toISOString(),
    priority: values.priority,
    ...(includeAssignee ? { assigned_user_id: optionalText(values.assigned_user_id) } : {}),
    notes: optionalText(values.notes),
  };
}
