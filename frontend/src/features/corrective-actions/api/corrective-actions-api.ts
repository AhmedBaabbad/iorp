import { apiClient } from "@/lib/api-client";
import type {
  CorrectiveActionDetail,
  CorrectiveActionListFilters,
  CorrectiveActionListItem,
  CreateCorrectiveActionRequest,
  UpdateCorrectiveActionStatusRequest,
} from "../types";

const CORRECTIVE_ACTIONS_PATH = "/corrective-actions";

export function getCorrectiveActions(filters: CorrectiveActionListFilters = {}) {
  const query = new URLSearchParams();

  if (filters.action_type) {
    query.set("action_type", filters.action_type);
  }

  if (filters.status) {
    query.set("status", filters.status);
  }

  if (filters.priority) {
    query.set("priority", filters.priority);
  }

  if (filters.source_type) {
    query.set("source_type", filters.source_type);
  }

  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient<CorrectiveActionListItem[]>(`${CORRECTIVE_ACTIONS_PATH}${suffix}`);
}

export function getCorrectiveActionById(correctiveActionId: string) {
  return apiClient<CorrectiveActionDetail>(
    `${CORRECTIVE_ACTIONS_PATH}/${correctiveActionId}`,
  );
}

export function createCorrectiveAction(payload: CreateCorrectiveActionRequest) {
  return apiClient<CorrectiveActionDetail>(CORRECTIVE_ACTIONS_PATH, {
    method: "POST",
    body: payload,
  });
}

export function updateCorrectiveActionStatus(
  correctiveActionId: string,
  payload: UpdateCorrectiveActionStatusRequest,
) {
  return apiClient<CorrectiveActionDetail>(
    `${CORRECTIVE_ACTIONS_PATH}/${correctiveActionId}`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}
