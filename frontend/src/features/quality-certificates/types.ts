// Certificates of Analysis (QUAL-COA-001): values copied from a closed inspection; numbered when issued.
import type { HistoryEntry } from "@/features/quality-checks/types";

export type CertificateStatus = "draft" | "issued" | "revoked";
export type CertificateAction = "edit" | "issue" | "revoke" | "replace";
export const CERTIFICATE_STATUSES: CertificateStatus[] = ["draft", "issued", "revoked"];

export type FrozenMeasurement = {
  code: string; name_ar: string; name_en: string; kind: "numeric" | "attribute"; unit: string | null; method: string | null;
  requirement: string | null; acceptance: string | null; target: string | null; lower: string | null; upper: string | null;
  count: number; minimum: string | null; maximum: string | null; mean: string | null;
  attribute_result: "conforming" | "nonconforming" | null; observation: string | null; status: "pass" | "fail" | "recorded" | "pending";
};

export type CertificateListItem = {
  id: string; certificate_no: string | null; status: CertificateStatus; quality_check_id: string; production_order_id: string | null;
  customer_name: string; batch_no: string; product_description: string; quantity: string; unit_label: string; inspection_code: string;
  issued_at: string | null; issued_by_name: string | null; supersedes_no: string | null; superseded_by_no: string | null;
  actions: CertificateAction[]; created_at: string;
};

export type Certificate = CertificateListItem & {
  production_order_item_id: string | null; customer_id: string | null; customer_po: string | null; delivery_ref: string | null;
  grade: string | null; production_date: string | null; inspection_date: string | null; package_count: number | null;
  sample_size: string | null; sampling_reference: string | null; retained_sample: boolean; retention_ref: string | null;
  deviation_note: string | null; remarks: string | null; inspection_result: string; specification_code: string | null;
  specification_revision: number | null; measurements: FrozenMeasurement[]; inspector_name: string | null; supersedes_id: string | null;
  prepared_by_name: string | null; revoked_at: string | null; revoked_by_name: string | null; revoke_reason: string | null; history: HistoryEntry[];
};

export type CertificateUpdate = Partial<Pick<Certificate, "customer_id" | "customer_name" | "customer_po" | "delivery_ref" | "batch_no"
  | "product_description" | "grade" | "production_date" | "inspection_date" | "quantity" | "unit_label" | "package_count" | "sample_size"
  | "sampling_reference" | "retained_sample" | "retention_ref" | "deviation_note" | "remarks">>;

export type CertificateSources = { certifiable: boolean; blocker: string | null; customers: { id: string; name: string }[] };
export type QualitySettings = { coa_prefix: string; coa_last_number: number };
