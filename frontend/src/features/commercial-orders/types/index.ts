type RequestedSpec = Record<string, unknown>;

export type CommercialOrderStatus =
  | "draft"
  | "confirmed"
  | "cancelled"
  | "converted_to_production";

export type CommercialOrderItem = {
  id?: string;
  commercial_order_id?: string;
  line_no: number;
  product_type: string;
  requested_spec_json: RequestedSpec | null;
  quantity: string;
  unit: string;
  agreed_unit_price: string | null;
  line_total: string | null;
};

export type CommercialOrderListItem = {
  id: string;
  organization_id: string;
  customer_id: string;
  quote_id: string | null;
  order_number: string;
  order_date: string;
  status: CommercialOrderStatus;
  requested_delivery_date: string | null;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type CommercialOrderData = CommercialOrderListItem & {
  notes: string | null;
  items: CommercialOrderItem[];
};

export type CreateCommercialOrderItemRequest = {
  line_no: number;
  product_type: string;
  requested_spec_json?: RequestedSpec | null;
  quantity: number;
  unit: string;
  agreed_unit_price?: number | null;
};

export type CreateCommercialOrderRequest = {
  customer_id: string;
  quote_id?: string | null;
  order_date: string;
  requested_delivery_date?: string | null;
  notes?: string | null;
  items: CreateCommercialOrderItemRequest[];
};

export type UpdateCommercialOrderRequest = {
  order_date?: string;
  requested_delivery_date?: string | null;
  notes?: string | null;
  status?: CommercialOrderStatus;
  items?: CreateCommercialOrderItemRequest[];
};

export type OrderDeletionImpact = {
  items: number;
  is_blocked: boolean;
};
