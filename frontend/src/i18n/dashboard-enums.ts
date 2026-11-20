/** A breakdown's type, not a second label dictionary. Dynamic cities/centers are handled as data. */
export const DASHBOARD_ENUM_FIELDS: Record<string, Record<string, string>> = {
  commercial: { pipeline: "customerRelationshipStage", quotes_by_status: "quoteStatus", orders_by_status: "commercialOrderStatus", samples_by_status: "sampleStatus" },
  production: { scrap_by_reason: "wasteRecordWasteCategory", downtime_by_category: "downtimeEventCategory", orders_by_status: "productionOrderStatus" },
  quality: { checks_by_result: "qualityCheckResult", checks_by_type: "qualityCheckCheckType", defects_by_category: "qualityDefectDefectCategory", rejections_by_reason: "qualityRejectionRejectionReason", ncrs_by_stage: "Stages" },
  shipping: { open_by_status: "status", returns_by_reason: "returnReason" },
  procurement: { approved_suppliers: "supplierStatus", open_purchase_orders: "orderStatus", draft_receipts: "receiptStatus" },
};
