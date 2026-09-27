import { getEnumLabel } from "@/i18n/enum-helpers";
import type { DowntimeCategory } from "../types";

export type WorkCenterOption = { id: string; code: string; name: string };

export type ProductionOrderOption = {
  id: string;
  production_order_number: string;
  product_type: string;
};

export const downtimeCategories: DowntimeCategory[] = [
  "machine",
  "material",
  "manpower",
  "quality",
  "utilities",
  "setup",
  "other",
];

export function formatCategory(category: DowntimeCategory, t: (key: string) => string) {
  return getEnumLabel("downtimeEvent", "category", category, t);
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

export function toIsoDatetime(value: string) {
  return new Date(value).toISOString();
}

export function toOptionalIsoDatetime(value: string) {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return null;
  }
  return new Date(trimmed).toISOString();
}
