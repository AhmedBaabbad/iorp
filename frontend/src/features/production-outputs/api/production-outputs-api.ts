import { apiClient } from "@/lib/api-client";
import type {
  CreateProductionOutputRequest,
  ProductionOutputData,
  ProductionOutputListFilters,
  ProductionOutputListItem,
} from "../types";

const PRODUCTION_OUTPUTS_PATH = "/production/production-outputs";

export function getProductionOutputs(filters: ProductionOutputListFilters = {}) {
  const query = new URLSearchParams();

  if (filters.production_order_id) {
    query.set("production_order_id", filters.production_order_id);
  }

  if (filters.shift_report_id) {
    query.set("shift_report_id", filters.shift_report_id);
  }

  if (filters.work_center_id) {
    query.set("work_center_id", filters.work_center_id);
  }

  if (filters.output_date) {
    query.set("output_date", filters.output_date);
  }

  if (filters.output_status) {
    query.set("output_status", filters.output_status);
  }

  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient<ProductionOutputListItem[]>(`${PRODUCTION_OUTPUTS_PATH}${suffix}`);
}

export function getProductionOutputById(productionOutputId: string) {
  return apiClient<ProductionOutputData>(
    `${PRODUCTION_OUTPUTS_PATH}/${productionOutputId}`,
  );
}

export function createProductionOutput(payload: CreateProductionOutputRequest) {
  return apiClient<ProductionOutputData>(PRODUCTION_OUTPUTS_PATH, {
    method: "POST",
    body: payload,
  });
}
