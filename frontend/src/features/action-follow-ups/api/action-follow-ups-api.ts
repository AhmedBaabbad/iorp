import { apiClient } from "@/lib/api-client";
import type {
  ActionFollowUpListItem,
  CreateActionFollowUpRequest,
} from "../types";

function actionFollowUpsPath(actionId: string) {
  return `/corrective-actions/${actionId}/follow-ups`;
}

export function getFollowUpsByAction(actionId: string) {
  return apiClient<ActionFollowUpListItem[]>(actionFollowUpsPath(actionId));
}

export function createFollowUp(
  actionId: string,
  payload: CreateActionFollowUpRequest,
) {
  return apiClient<ActionFollowUpListItem>(actionFollowUpsPath(actionId), {
    method: "POST",
    body: payload,
  });
}
