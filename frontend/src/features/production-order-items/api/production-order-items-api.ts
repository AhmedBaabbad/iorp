import { apiClient } from "@/lib/api-client";
import type {
  CreateProductionOrderItemRequest,
  ProductionOrderItemListItem,
} from "../types";

function productionOrderItemsPath(productionOrderId: string) {
  return `/production/production-orders/${productionOrderId}/items`;
}

export function getItemsByOrder(productionOrderId: string) {
  return apiClient<ProductionOrderItemListItem[]>(
    productionOrderItemsPath(productionOrderId),
  );
}

export function createItem(
  productionOrderId: string,
  payload: CreateProductionOrderItemRequest,
) {
  return apiClient<ProductionOrderItemListItem>(
    productionOrderItemsPath(productionOrderId),
    {
      method: "POST",
      body: payload,
    },
  );
}
