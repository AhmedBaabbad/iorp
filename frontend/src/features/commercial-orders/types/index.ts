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

export type SalesOrderAction = "edit" | "confirm" | "cancel" | "delete" | "transfer" | "revise";

export type CommercialOrderListItem = {
  id: string;
  organization_id: string;
  customer_id: string;
  quote_id: string | null;
  order_number: string;
  order_date: string;
  status: CommercialOrderStatus;
  requested_delivery_date: string | null;
  customer_reference?: string | null;
  revision?: number;
  /** On a list page: the customer and the quotation's number, read once for the page. */
  customer_name?: string | null;
  customer_code?: string | null;
  quote_number?: string | null;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type SalesOrderHistoryEntry = {
  action: string;
  from_status: string | null;
  to_status: string;
  revision: number;
  reason: string | null;
  actor_name: string | null;
  created_at: string;
};

export type CommercialOrderData = CommercialOrderListItem & {
  confirm_blocked_reason?: "preparer" | null;
  currency?: string | null;
  confirmed_at?: string | null;
  allowed_actions?: SalesOrderAction[];
  /** {line id: quantity the production demands in force took} */
  transferred_quantities?: Record<string, string>;
  fulfilment?: "none" | "partial" | "full";
  history?: SalesOrderHistoryEntry[];
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
  customer_reference?: string | null;
  currency?: string | null;
  order_date: string;
  requested_delivery_date?: string | null;
  notes?: string | null;
  items: CreateCommercialOrderItemRequest[];
};

/** A draft only; the status changes through confirm, revise and cancel. */
export type UpdateCommercialOrderRequest = {
  quote_id?: string | null;
  customer_reference?: string | null;
  currency?: string | null;
  order_date?: string;
  requested_delivery_date?: string | null;
  notes?: string | null;
  items?: CreateCommercialOrderItemRequest[];
};

export type OrderDeletionImpact = {
  items: number;
  is_blocked: boolean;
};
