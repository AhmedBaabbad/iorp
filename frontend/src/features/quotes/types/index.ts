type RequestedSpec = Record<string, unknown>;

export type QuoteStatus = "draft" | "issued" | "accepted" | "rejected" | "expired";

export type QuoteItem = {
  id?: string;
  quote_id?: string;
  line_no: number;
  product_type: string;
  requested_spec_json: RequestedSpec | null;
  quantity: string;
  unit: string;
  unit_price: string;
  line_total: string;
  description_ar?: string | null;
  description_en?: string | null;
};

export type QuoteSampleOption = {
  id: string;
  customer_id: string;
  sample_code: string;
  product_type: string;
};

export type QuoteListItem = {
  id: string;
  organization_id: string;
  customer_id: string;
  sample_id: string | null;
  quote_number: string;
  issue_date: string;
  valid_until: string;
  status: QuoteStatus;
  currency: string;
  /** On a list page: the customer, read once for the page. */
  customer_name?: string | null;
  customer_code?: string | null;
  subtotal_amount: string;
  discount_amount: string;
  tax_amount: string;
  total_amount: string;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

/** One step of a quotation's or a sales order's life (SALES-001). */
export type StatusHistoryEntry = {
  action: string;
  from_status: string | null;
  to_status: string;
  revision: number;
  reason: string | null;
  actor_name: string | null;
  created_at: string;
};

export type QuoteAction = "edit" | "issue" | "accept" | "reject" | "expire" | "revise" | "create_order";

export type QuoteData = QuoteListItem & {
  revision?: number;
  allowed_actions?: QuoteAction[];
  history?: StatusHistoryEntry[];
  orders?: { id: string; order_number: string; status: string }[];
  notes: string | null;
  tax_rate?: string | null;
  attention?: string | null;
  subject?: string | null;
  items: QuoteItem[];
};

export type CreateQuoteItemRequest = {
  line_no: number;
  product_type: string;
  requested_spec_json?: RequestedSpec | null;
  quantity: number;
  unit: string;
  unit_price: number;
  description_ar?: string | null;
  description_en?: string | null;
};

export type CreateQuoteRequest = {
  customer_id: string;
  sample_id?: string | null;
  issue_date: string;
  valid_until: string;
  currency: string;
  discount_amount: number;
  // The server computes the VAT amount from the rate.
  tax_rate: number;
  tax_amount: number;
  attention?: string | null;
  subject?: string | null;
  notes?: string | null;
  items: CreateQuoteItemRequest[];
};

export type UpdateQuoteRequest = {
  sample_id?: string | null;
  issue_date?: string;
  valid_until?: string;
  currency?: string;
  discount_amount?: number;
  tax_rate?: number;
  tax_amount?: number;
  attention?: string | null;
  subject?: string | null;
  notes?: string | null;
  items?: CreateQuoteItemRequest[];
};

export type QuoteTerm = { title_ar: string | null; title_en: string | null; body_ar: string | null; body_en: string | null; is_active: boolean };

export type DocumentLanguage = "ar" | "en";
export type QuoteSettings = {
  /** Every quotation is printed in this language, with the settings written in it (nothing from the other one). */
  document_language: DocumentLanguage;
  signature_title_ar: string | null;
  signature_title_en: string | null;
  show_preparer_name: boolean;
  terms: QuoteTerm[];
};

export type QuoteTotalsData = {
  subtotal: string | number;
  discount: string | number;
  tax: string | number;
  total: string | number;
  currency: string;
};

export type QuoteDeletionImpact = {
  items: number;
  orders: number;
  is_blocked: boolean;
};
