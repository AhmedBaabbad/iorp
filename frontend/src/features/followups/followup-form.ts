import { optionalText, toDatetimeLocalValue } from "@/lib/utils";
import type { FollowUpCreateRequest } from "@/types/followups";

export type FollowUpFormValues = {
  due_date: string;
  priority: FollowUpCreateRequest["priority"];
  reason: string;
  notes: string;
};

export function createDefaultFollowUpFormValues(): FollowUpFormValues {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);

  return {
    due_date: toDatetimeLocalValue(tomorrow),
    priority: "medium",
    reason: "",
    notes: "",
  };
}

export function toFollowUpCreateRequest(
  values: FollowUpFormValues,
  assignedUserId: string,
): FollowUpCreateRequest {
  return {
    assigned_user_id: assignedUserId,
    due_date: new Date(values.due_date).toISOString(),
    priority: values.priority,
    reason: values.reason.trim(),
    notes: optionalText(values.notes),
  };
}
