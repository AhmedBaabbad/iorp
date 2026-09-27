import { getEnumLabel } from "@/i18n/enum-helpers";
import type { WasteCategory } from "../types";

export type WorkCenterOption = { id: string; code: string; name: string };

export type ProductionOrderOption = {
  id: string;
  production_order_number: string;
  product_type: string;
};

export const wasteCategories: WasteCategory[] = [
  "startup_loss",
  "trim_loss",
  "setup_loss",
  "rejected_output",
  "breakage",
  "rewinding_loss",
  "end_of_roll_loss",
  "material_loss",
  "contamination_loss",
  "other",
];

export function formatWasteCategory(category: WasteCategory, t: (key: string) => string) {
  return getEnumLabel("wasteRecord", "wasteCategory", category, t);
}

export function formatWorkCenterLabel(
  workCenters: WorkCenterOption[],
  workCenterId: string,
) {
  const workCenter = workCenters.find((item) => item.id === workCenterId);
  return workCenter ? `${workCenter.code} - ${workCenter.name}` : workCenterId;
}

export function formatProductionOrderLabel(
  productionOrders: ProductionOrderOption[],
  productionOrderId: string,
) {
  const order = productionOrders.find((item) => item.id === productionOrderId);
  return order
    ? `${order.production_order_number} - ${order.product_type}`
    : productionOrderId;
}

export function truncateText(value: string, maxLength: number) {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 1)}...`;
}
