import { apiClient } from "@/lib/api-client";
import type { DashboardSummary } from "../types";

export function getDashboardSummary(token?: string | null) {
  return apiClient<DashboardSummary>("/dashboard/summary", { token });
}
