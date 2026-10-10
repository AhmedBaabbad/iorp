"use client";

import type { CommercialOrderData } from "../types";
import { CommercialOrderForm } from "./CommercialOrderForm";

/** A draft sales order, edited with the same form it was written with (SALES-001). */
export function CommercialOrderEditForm({ order }: { order: CommercialOrderData }) {
  return <CommercialOrderForm order={order} />;
}
