export type WorkCenterOption = { id: string; code: string; name: string };

export type ProductionOrderOption = {
  id: string;
  production_order_number: string;
  product_type: string;
};

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
  return order ? `${order.production_order_number} - ${order.product_type}` : productionOrderId;
}
