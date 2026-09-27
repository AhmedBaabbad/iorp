import { apiClient } from "@/lib/api-client";
import type {
  ClosureVerification,
  CreateClosureVerificationRequest,
} from "../types";

function closureVerificationPath(actionId: string) {
  return `/corrective-actions/${actionId}/closure`;
}

export function getClosureVerification(actionId: string) {
  return apiClient<ClosureVerification>(closureVerificationPath(actionId));
}

export function createClosureVerification(
  actionId: string,
  payload: CreateClosureVerificationRequest,
) {
  return apiClient<ClosureVerification>(closureVerificationPath(actionId), {
    method: "POST",
    body: payload,
  });
}
