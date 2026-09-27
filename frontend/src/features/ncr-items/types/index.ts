export type NcrItemListItem = {
  id: string;
  non_conformance_report_id: string;
  line_no: number;
  item_reference: string | null;
  item_name: string;
  quantity_affected: string | null;
  unit: string | null;
  issue_description: string;
  created_at: string;
  updated_at: string;
  notes?: string | null;
};

export type NcrItemData = NcrItemListItem & {
  notes: string | null;
};

export type CreateNcrItemRequest = {
  item_name: string;
  issue_description: string;
  item_reference?: string | null;
  quantity_affected?: number | null;
  unit?: string | null;
  notes?: string | null;
};
