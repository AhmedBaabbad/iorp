# PROD-QUALITY-FIX-001 ? Static consumer evidence

Captured 2026-10-10 from the working tree. Documentation only. Export-name matches include re-exports and can include same-name functions; direct URL matches and backend references supplement them. This is source evidence, not proof of external-client coverage or runtime success.

## Frontend API and shared-catalogue references

### getDowntimeEvents

Definition: `frontend/src/features/downtime-events/api.ts`

- `frontend/src/features/downtime-events/components/DowntimeEventsList.tsx`
- `frontend/src/features/downtime-events/index.ts`

### getDowntimeSummary

Definition: `frontend/src/features/downtime-events/api.ts`

- `frontend/src/features/downtime-events/components/DowntimeEventsList.tsx`
- `frontend/src/features/downtime-events/components/OrderDowntimeSection.tsx`
- `frontend/src/features/downtime-events/index.ts`

### getDowntimeEventById

Definition: `frontend/src/features/downtime-events/api.ts`

- `frontend/src/features/downtime-events/components/DowntimeEventDetail.tsx`
- `frontend/src/features/downtime-events/components/DowntimeEventForm.tsx`
- `frontend/src/features/downtime-events/index.ts`

### getOrderRuns

Definition: `frontend/src/features/downtime-events/api.ts`

- `frontend/src/features/downtime-events/components/DowntimeEventForm.tsx`
- `frontend/src/features/waste-records/api.ts`
- `frontend/src/features/waste-records/components/WasteRecordForm.tsx`

### getProducts

Definition: `frontend/src/features/masterdata/api.ts`

- `frontend/src/features/masterdata/catalog.ts`
- `frontend/src/features/masterdata/components/Products.tsx`

### getProduct

Definition: `frontend/src/features/masterdata/api.ts`

- `frontend/src/features/masterdata/components/Products.tsx`

### getLegacyValues

Definition: `frontend/src/features/masterdata/api.ts`

- `frontend/src/features/masterdata/components/Products.tsx`

### getBusinessSettings

Definition: `frontend/src/features/masterdata/api.ts`

- `frontend/src/features/masterdata/catalog.ts`
- `frontend/src/features/masterdata/components/GeneralSettings.tsx`

### getListItems

Definition: `frontend/src/features/masterdata/api.ts`

- `frontend/src/features/masterdata/catalog.ts`
- `frontend/src/features/masterdata/components/ReferenceLists.tsx`

### getListLegacy

Definition: `frontend/src/features/masterdata/api.ts`

- `frontend/src/features/masterdata/components/ReferenceLists.tsx`

### useListItems

Definition: `frontend/src/features/masterdata/catalog.ts`

- `frontend/src/features/masterdata/components/ListSelect.tsx`
- `frontend/src/features/masterdata/index.ts`

### useListName

Definition: `frontend/src/features/masterdata/catalog.ts`

- `frontend/src/features/customers/customer-detail-page.tsx`
- `frontend/src/features/customers/customers-list-page.tsx`
- `frontend/src/features/interactions/customer-interactions-page.tsx`
- `frontend/src/features/masterdata/index.ts`
- `frontend/src/features/procurement/components/Suppliers.tsx`
- `frontend/src/features/shipments/components/ShipmentDetail.tsx`

### useProducts

Definition: `frontend/src/features/masterdata/catalog.ts`

- `frontend/src/features/commercial-orders/components/CommercialOrderForm.tsx`
- `frontend/src/features/commercial-orders/components/sales-lifecycle.tsx`
- `frontend/src/features/masterdata/components/ProductSelect.tsx`
- `frontend/src/features/masterdata/index.ts`
- `frontend/src/features/production-demands/form.tsx`
- `frontend/src/features/quotes/components/QuoteEditForm.tsx`
- `frontend/src/features/quotes/components/QuoteForm.tsx`

### useBusinessSettings

Definition: `frontend/src/features/masterdata/catalog.ts`

- `frontend/src/features/commercial-orders/components/CommercialOrderForm.tsx`
- `frontend/src/features/masterdata/index.ts`
- `frontend/src/features/procurement/components/PurchaseOrders.tsx`
- `frontend/src/features/quotes/components/QuoteEditForm.tsx`
- `frontend/src/features/quotes/components/QuoteForm.tsx`

### useProductName

Definition: `frontend/src/features/masterdata/catalog.ts`

- `frontend/src/features/commercial-orders/components/CommercialOrderDetail.tsx`
- `frontend/src/features/commercial-orders/components/OrderItemsTable.tsx`
- `frontend/src/features/masterdata/index.ts`
- `frontend/src/features/procurement/components/Materials.tsx`
- `frontend/src/features/production-demands/form.tsx`
- `frontend/src/features/production-demands/from-sales-order.tsx`
- `frontend/src/features/production-orders/components/ProductionOrderDetail.tsx`
- `frontend/src/features/production-orders/components/ProductionOrdersList.tsx`
- `frontend/src/features/quality-specifications/components/SpecificationDetail.tsx`
- `frontend/src/features/quality-specifications/components/SpecificationsList.tsx`
- `frontend/src/features/quotes/components/QuoteItemsTable.tsx`
- `frontend/src/features/samples/components/SamplesList.tsx`

### getNcrReports

Definition: `frontend/src/features/ncr-reports/api.ts`

- `frontend/src/features/ncr-reports/components/NcrReportsList.tsx`

### getNcrReport

Definition: `frontend/src/features/ncr-reports/api.ts`

- `frontend/src/features/ncr-reports/components/NcrReportDetail.tsx`
- `frontend/src/features/ncr-reports/components/NcrReportForm.tsx`

### getNcrSuppliers

Definition: `frontend/src/features/ncr-reports/api.ts`

- `frontend/src/features/ncr-reports/components/NcrReportForm.tsx`

### getNcrUsers

Definition: `frontend/src/features/ncr-reports/api.ts`

- `frontend/src/features/ncr-reports/components/NcrReportDetail.tsx`
- `frontend/src/features/ncr-reports/components/NcrReportForm.tsx`

### getCorrectiveActions

Definition: `frontend/src/features/ncr-reports/api.ts`

- `frontend/src/features/ncr-reports/components/CorrectiveActionsList.tsx`

### getCapaAlerts

Definition: `frontend/src/features/ncr-reports/api.ts`

- `frontend/src/features/ncr-reports/use-capa-alerts.ts`

### demandsApi

Definition: `frontend/src/features/production-demands/api.ts`

- `frontend/src/features/production-demands/demand-allocations.tsx`
- `frontend/src/features/production-demands/detail.tsx`
- `frontend/src/features/production-demands/form.tsx`
- `frontend/src/features/production-demands/from-sales-order.tsx`
- `frontend/src/features/production-demands/list.tsx`
- `frontend/src/features/production-orders/components/OrderLines.tsx`

### getItemsByOrder

Definition: `frontend/src/features/production-order-items/api/production-order-items-api.ts`

- `frontend/src/features/production-order-items/components/ProductionOrderItemsList.tsx`
- `frontend/src/features/production-order-items/index.ts`

### getProductionOrders

Definition: `frontend/src/features/production-orders/api/production-orders-api.ts`

- `frontend/src/features/downtime-events/components/DowntimeEventForm.tsx`
- `frontend/src/features/downtime-events/components/DowntimeEventsList.tsx`
- `frontend/src/features/production-orders/components/ProductionOrdersList.tsx`
- `frontend/src/features/production-orders/index.ts`
- `frontend/src/features/waste-records/components/WasteRecordForm.tsx`
- `frontend/src/features/waste-records/components/WasteRecordsList.tsx`

### getProductionOrderById

Definition: `frontend/src/features/production-orders/api/production-orders-api.ts`

- `frontend/src/features/production-orders/components/ProductionOrderDetail.tsx`
- `frontend/src/features/production-orders/index.ts`
- `frontend/src/features/waste-records/components/WasteRecordForm.tsx`

### getProductionOrderStatusHistory

Definition: `frontend/src/features/production-orders/api/production-orders-api.ts`

- `frontend/src/features/production-orders/components/OrderStatusTimeline.tsx`

### getOrderResult

Definition: `frontend/src/features/production-results/api.ts`

- `frontend/src/features/production-results/components/CloseResultDialog.tsx`
- `frontend/src/features/production-results/components/OrderResultSection.tsx`
- `frontend/src/features/production-results/index.ts`

### getResultsOverview

Definition: `frontend/src/features/production-results/api.ts`

- `frontend/src/features/production-results/components/ResultsList.tsx`
- `frontend/src/features/production-results/index.ts`

### getCertificates

Definition: `frontend/src/features/quality-certificates/api.ts`

- `frontend/src/features/quality-certificates/components/CertificatesList.tsx`
- `frontend/src/features/quality-certificates/components/CheckCertificatesSection.tsx`

### getCertificate

Definition: `frontend/src/features/quality-certificates/api.ts`

- `frontend/src/features/quality-certificates/components/CertificateDetail.tsx`

### getCertificateSources

Definition: `frontend/src/features/quality-certificates/api.ts`

- `frontend/src/features/quality-certificates/components/CheckCertificatesSection.tsx`

### getQualitySettings

Definition: `frontend/src/features/quality-certificates/api.ts`

- `frontend/src/features/quality-certificates/components/CertificatesList.tsx`

### getQualityChecks

Definition: `frontend/src/features/quality-checks/api/quality-checks-api.ts`

- `frontend/src/features/order-quality/OrderQualitySection.tsx`
- `frontend/src/features/quality-checks/components/QualityChecksList.tsx`
- `frontend/src/features/quality-checks/index.ts`

### getQualityCheckById

Definition: `frontend/src/features/quality-checks/api/quality-checks-api.ts`

- `frontend/src/features/quality-checks/components/QualityCheckDetail.tsx`
- `frontend/src/features/quality-checks/components/QualityCheckForm.tsx`
- `frontend/src/features/quality-checks/index.ts`
- `frontend/src/features/quality-rejections/components/QualityRejectionForm.tsx`

### getInspectableOrders

Definition: `frontend/src/features/quality-checks/api/quality-checks-api.ts`

- `frontend/src/features/quality-checks/components/QualityCheckForm.tsx`
- `frontend/src/features/quality-checks/index.ts`
- `frontend/src/features/quality-rejections/components/QualityRejectionForm.tsx`

### getInspectableSamples

Definition: `frontend/src/features/quality-checks/api/quality-checks-api.ts`

- `frontend/src/features/quality-checks/components/QualityCheckForm.tsx`
- `frontend/src/features/quality-checks/index.ts`

### getPlanCandidates

Definition: `frontend/src/features/quality-checks/api/quality-checks-api.ts`

- `frontend/src/features/quality-checks/components/MeasurementsSection.tsx`

### getAwaitingReturns

Definition: `frontend/src/features/quality-checks/api/quality-checks-api.ts`

- `frontend/src/features/quality-checks/components/QualityReturnsList.tsx`

### getBatchShipments

Definition: `frontend/src/features/quality-checks/api/quality-checks-api.ts`

- `frontend/src/features/quality-checks/components/ReturnInspection.tsx`

### getAwaitingLots

Definition: `frontend/src/features/quality-checks/api/quality-checks-api.ts`

- `frontend/src/features/quality-checks/components/IncomingInspection.tsx`

### getDefectsByCheck

Definition: `frontend/src/features/quality-defects/api/quality-defects-api.ts`

- `frontend/src/features/quality-defects/components/QualityDefectsList.tsx`
- `frontend/src/features/quality-defects/index.ts`

### getDefectById

Definition: `frontend/src/features/quality-defects/api/quality-defects-api.ts`

- `frontend/src/features/quality-defects/index.ts`

### getQualityRejections

Definition: `frontend/src/features/quality-rejections/api/quality-rejections-api.ts`

- `frontend/src/features/order-quality/OrderQualitySection.tsx`
- `frontend/src/features/quality-rejections/components/QualityRejectionsList.tsx`
- `frontend/src/features/quality-rejections/index.ts`

### getQualityRejectionById

Definition: `frontend/src/features/quality-rejections/api/quality-rejections-api.ts`

- `frontend/src/features/quality-rejections/components/QualityRejectionDetail.tsx`
- `frontend/src/features/quality-rejections/components/QualityRejectionForm.tsx`
- `frontend/src/features/quality-rejections/index.ts`

### getParameters

Definition: `frontend/src/features/quality-specifications/api.ts`

- `frontend/src/features/quality-specifications/components/SpecificationForm.tsx`
- `frontend/src/features/quality-specifications/components/TestParametersPage.tsx`

### getSpecifications

Definition: `frontend/src/features/quality-specifications/api.ts`

- `frontend/src/features/quality-specifications/components/SpecificationsList.tsx`

### getSpecification

Definition: `frontend/src/features/quality-specifications/api.ts`

- `frontend/src/features/quality-specifications/components/SpecificationDetail.tsx`
- `frontend/src/features/quality-specifications/components/SpecificationForm.tsx`

### getShifts

Definition: `frontend/src/features/shifts/api/shifts-api.ts`

- `frontend/src/features/shifts/components/ShiftsList.tsx`
- `frontend/src/features/shifts/index.ts`

### getShiftById

Definition: `frontend/src/features/shifts/api/shifts-api.ts`

- `frontend/src/features/shifts/components/ShiftDetail.tsx`
- `frontend/src/features/shifts/components/ShiftEditPage.tsx`
- `frontend/src/features/shifts/index.ts`

### getShiftDeletionImpact

Definition: `frontend/src/features/shifts/api/shifts-api.ts`

- `frontend/src/features/shifts/components/ShiftsList.tsx`
- `frontend/src/features/shifts/index.ts`

### getWasteRecords

Definition: `frontend/src/features/waste-records/api.ts`

- `frontend/src/features/waste-records/components/WasteRecordsList.tsx`
- `frontend/src/features/waste-records/index.ts`

### getWasteRecordById

Definition: `frontend/src/features/waste-records/api.ts`

- `frontend/src/features/waste-records/components/WasteRecordDetail.tsx`
- `frontend/src/features/waste-records/components/WasteRecordForm.tsx`
- `frontend/src/features/waste-records/index.ts`

### getWasteSummary

Definition: `frontend/src/features/waste-records/api.ts`

- `frontend/src/features/waste-records/components/OrderWasteSection.tsx`
- `frontend/src/features/waste-records/index.ts`

### getOrderRuns

Definition: `frontend/src/features/waste-records/api.ts`

- `frontend/src/features/downtime-events/api.ts`
- `frontend/src/features/downtime-events/components/DowntimeEventForm.tsx`
- `frontend/src/features/waste-records/components/WasteRecordForm.tsx`

### getWorkCenters

Definition: `frontend/src/features/work-centers/api/work-centers-api.ts`

- `frontend/src/features/downtime-events/components/DowntimeEventForm.tsx`
- `frontend/src/features/downtime-events/components/DowntimeEventsList.tsx`
- `frontend/src/features/production-demands/planning-allocation.tsx`
- `frontend/src/features/production-orders/components/ProductionOrderDetail.tsx`
- `frontend/src/features/production-orders/components/ProductionOrdersList.tsx`
- `frontend/src/features/waste-records/components/WasteRecordForm.tsx`
- `frontend/src/features/waste-records/components/WasteRecordsList.tsx`
- `frontend/src/features/work-centers/components/WorkCentersList.tsx`
- `frontend/src/features/work-centers/index.ts`

### getWorkCenterById

Definition: `frontend/src/features/work-centers/api/work-centers-api.ts`

- `frontend/src/features/work-centers/components/WorkCenterDetail.tsx`
- `frontend/src/features/work-centers/components/WorkCenterEditPage.tsx`
- `frontend/src/features/work-centers/index.ts`

### getWorkCenterDeleteSummary

Definition: `frontend/src/features/work-centers/api/work-centers-api.ts`

- `frontend/src/features/work-centers/components/WorkCentersList.tsx`
- `frontend/src/features/work-centers/index.ts`

## Direct endpoint and shared component references

### frontend/src/components/forms/UnitSelect.tsx

- Line 13: `export function UnitSelect({ value, onChange, disabled, groups, required = true, className, style, ariaLabel, placeholder }: {`

### frontend/src/components/layout/menu-icons.tsx

- Line 77: `"/production/planning": IconPlanning, "/production-orders": IconWorkOrder, "/production-results": IconBoxCheck, "/production-reports": IconReport,`

### frontend/src/components/layout/page-frame.tsx

- Line 158: `{ href: "/production/planning", labelKey: "links.planning", permission: P.PLANNING_READ },`

### frontend/src/features/commercial-orders/components/CommercialOrderForm.tsx

- Line 10: `import { UnitSelect } from "@/components/forms/UnitSelect";`
- Line 13: `import { ProductSelect, useBusinessSettings, useProducts } from "@/features/masterdata";`
- Line 228: `<ProductSelect value={line.product_type} disabled={busy} ariaLabel={t("items.fields.productType")}`
- Line 236: `<UnitSelect className="" value={line.unit} disabled={busy} ariaLabel={t("items.fields.unit")} onChange={(unit) => setLine(index, { unit })} />`

### frontend/src/features/downtime-events/api.ts

- Line 44: `return apiClient<RunOption[]>('/production/runs?production_order_id=${orderId}');`

### frontend/src/features/masterdata/components/Products.tsx

- Line 8: `import { UnitSelect } from "@/components/forms/UnitSelect";`
- Line 172: `<label className={s.field}>{t("fields.unit")}<UnitSelect value={v.default_unit ?? ""} onChange={u => setV({ ...v, default_unit: u || null })}`
- Line 194: `{p.kind === "number" && <label className={s.field}>{t("template.unit")}<UnitSelect value={p.unit ?? ""} onChange={u => setProp(i, { unit: u || null })}`

### frontend/src/features/masterdata/components/ProductSelect.tsx

- Line 17: `export function ProductSelect({ id, value, onChange, kind, required = true, disabled, ariaLabel, className, style }: {`

### frontend/src/features/masterdata/index.ts

- Line 3: `export { ProductSelect } from "./components/ProductSelect";`

### frontend/src/features/ncr-reports/api.ts

- Line 48: `export const getCorrectiveActions = (filters: ActionFilters = {}) => apiClient<CorrectiveAction[]>('/quality/ncr-actions${query(filters)}');`
- Line 49: `export const getCapaAlerts = () => apiClient<CapaAlerts>("/quality/ncr-actions/alerts");`

### frontend/src/features/ncr-reports/components/NcrReportDetail.tsx

- Line 7: `import { UnitSelect } from "@/components/forms/UnitSelect";`
- Line 460: `<label className={s.field}>{t("itemFields.unit")}<UnitSelect value={v.unit} onChange={u => set("unit", u)} ariaLabel={t("itemFields.unit")} placeholder="—" required={false} /></label>`

### frontend/src/features/ncr-reports/components/NcrReportForm.tsx

- Line 8: `import { UnitSelect } from "@/components/forms/UnitSelect";`
- Line 152: `<label className={s.field}>{t("itemFields.unit")}<UnitSelect value={item.unit} onChange={u => setItem(i, "unit", u)} ariaLabel={t("itemFields.unit")} placeholder="—" required={false} /></label>`

### frontend/src/features/procurement/components/Materials.tsx

- Line 6: `import { UnitSelect } from "@/components/forms/UnitSelect";`
- Line 9: `import { ProductSelect, useProductName } from "@/features/masterdata";`
- Line 84: `<label className={s.field}>{t("fields.unit")}<UnitSelect value={v.unit} onChange={u => setV({ ...v, unit: u })} ariaLabel={t("fields.unit")} /></label>`
- Line 85: `<label className={s.field}>{t("fields.spec_product_type")}<ProductSelect ariaLabel={t("fields.spec_product_type")} kind="material" required={false}`

### frontend/src/features/procurement/components/PurchaseOrders.tsx

- Line 8: `import { UnitSelect } from "@/components/forms/UnitSelect";`
- Line 272: `<label className={s.field}>{t("orders.fields.unit")}<UnitSelect value={l.unit} onChange={u => setLine(i, "unit", u)} ariaLabel={t("orders.fields.unit")} /></label>`

### frontend/src/features/procurement/components/Receipts.tsx

- Line 8: `import { UnitSelect } from "@/components/forms/UnitSelect";`
- Line 263: `: <UnitSelect value={l.unit} onChange={u => setLine(i, "unit", u)} ariaLabel={t("fields.unit")} />}</label>`
- Line 267: `<UnitSelect value={l.weight_unit} onChange={u => setLine(i, "weight_unit", u || "kg")} groups={["weight"]} ariaLabel={t("fields.weight_unit")} /></label>`

### frontend/src/features/production-demands/demand-allocations.tsx

- Line 41: `{showAllocateLink && <p><Link className={'${s.button} ${s.primary}'} href={'/production/planning?search=${encodeURIComponent(demand.demand_number)}'}>{t("allocateNow")}</Link></p>}`

### frontend/src/features/production-demands/form.tsx

- Line 7: `import { ProductSelect, useProductName, useProducts } from "@/features/masterdata";`
- Line 133: `<label className={s.field}>{t("productType")}<ProductSelect ariaLabel={t("productType")} value={row.product_type ?? ""}`

### frontend/src/features/production-demands/planning-allocation.tsx

- Line 62: `apiClient<{ lines: PreviewLine[] }>("/production/planning/preview-production-order", { method: "POST", body: { allocations: JSON.parse(payload) } })`
- Line 78: `const order = await apiClient<{ id: string }>("/production/planning/create-production-order", { method: "POST", body: {`

### frontend/src/features/production-execution/ExecutionPanel.tsx

- Line 73: `if (hasPermission(permissions, P.SHIFTS_READ)) requests.push(apiClient<Option[]>(base + "shift-definitions").then(setShifts));`
- Line 75: `if (orderId && hasPermission(permissions, P.WORK_CENTERS_READ)) requests.push(apiClient<Option[]>(base + "work-centers").then(setCenters));`
- Line 76: `if (orderId && hasPermission(permissions, P.ROSTERS_READ)) requests.push(apiClient<RecordData[]>(base + "shift-rosters").then(setRosters));`

### frontend/src/features/production-order-items/api/production-order-items-api.ts

- Line 8: `return '/production/production-orders/${productionOrderId}/items';`

### frontend/src/features/production-orders/api/production-orders-api.ts

- Line 11: `const PRODUCTION_ORDERS_PATH = "/production/production-orders";`

### frontend/src/features/production-orders/components/ProductionOrderForm.tsx

- Line 10: `useEffect(() => { router.replace("/production/planning"); }, [router]);`

### frontend/src/features/production-orders/components/ProductionOrdersList.tsx

- Line 153: `<Link href="/production/planning" style={sharedStyles.button}>`
- Line 239: `<Link href="/production/planning" style={sharedStyles.button}>`

### frontend/src/features/production-results/api.ts

- Line 4: `const base = (orderId: string) => '/production/production-orders/${orderId}/result';`
- Line 30: `return apiClient<ResultOverviewRow[]>('/production/production-results${status ? '?status=${status}' : ""}');`

### frontend/src/features/quality-certificates/api.ts

- Line 4: `const PATH = "/quality/quality-certificates";`
- Line 22: `export const getQualitySettings = () => apiClient<QualitySettings>("/quality/quality-settings");`
- Line 23: `export const updateQualitySettings = (body: Partial<QualitySettings>) => apiClient<QualitySettings>("/quality/quality-settings", { method: "PATCH", body });`

### frontend/src/features/quality-checks/api/quality-checks-api.ts

- Line 7: `const PATH = "/quality/quality-checks";`
- Line 66: `return apiClient<AwaitingReturn[]>('/quality/returns/awaiting?q=${encodeURIComponent(search)}');`
- Line 70: `return apiClient<QualityCheckData>('/quality/returns/lines/${returnLineId}/inspection', { method: "POST" });`
- Line 83: `return apiClient<AwaitingReceipt[]>('/quality/incoming/awaiting?q=${encodeURIComponent(search)}');`
- Line 87: `return apiClient<QualityCheckData>('/quality/incoming/lines/${receiptLineId}/inspection', { method: "POST" });`

### frontend/src/features/quality-defects/api/quality-defects-api.ts

- Line 9: `return '/quality/quality-checks/${qualityCheckId}/defects';`
- Line 27: `return apiClient<QualityDefectData>('/quality/quality-defects/${defectId}');`

### frontend/src/features/quality-rejections/api/quality-rejections-api.ts

- Line 7: `const PATH = "/quality/quality-rejections";`

### frontend/src/features/quality-specifications/api.ts

- Line 4: `const PARAMS = "/quality/quality-test-parameters";`
- Line 5: `const SPECS = "/quality/quality-specifications";`

### frontend/src/features/quality-specifications/components/SpecificationForm.tsx

- Line 9: `import { ProductSelect } from "@/features/masterdata";`
- Line 97: `<label className={s.field}>{t("fields.productType")}<ProductSelect ariaLabel={t("fields.productType")} value={header.product_type} disabled={busy || locked}`

### frontend/src/features/quotes/components/QuoteEditForm.tsx

- Line 20: `import { LineDescriptionFields, QuoteHeadingFields, UnitSelect } from "./QuoteLineFields";`
- Line 22: `import { ProductSelect, useBusinessSettings, useProducts } from "@/features/masterdata";`
- Line 491: `<ProductSelect style={sharedStyles.input} value={item.product_type} disabled={isSubmitting}`
- Line 521: `<UnitSelect value={item.unit} disabled={isSubmitting}`

### frontend/src/features/quotes/components/QuoteForm.tsx

- Line 19: `import { LineDescriptionFields, QuoteHeadingFields, UnitSelect } from "./QuoteLineFields";`
- Line 21: `import { ProductSelect, useBusinessSettings, useProducts } from "@/features/masterdata";`
- Line 423: `<ProductSelect style={sharedStyles.input} value={item.product_type} disabled={isSubmitting}`
- Line 453: `<UnitSelect value={item.unit} disabled={isSubmitting}`

### frontend/src/features/quotes/components/QuoteLineFields.tsx

- Line 7: `export { UnitSelect } from "@/components/forms/UnitSelect";`

### frontend/src/features/reports/api.ts

- Line 7: `export const getLookups = (kind: string, query: string, module: string) => apiClient<{ id: string; label: string }[]>('/reports/${module}/lookups/${kind}?q=${encodeURIComponent(query)}');`

### frontend/src/features/reports/ReportForm.tsx

- Line 4: `import { Definition, Schema, getDefinitions, getLookups, reportRequest } from './api';`
- Line 18: `const timer = setTimeout(() => { getLookups(kind, query, module).then(v => { if (active) setOptions(v); }).catch(() => { if (active) setOptions([]); }); }, 200);`

### frontend/src/features/samples/components/SampleEditForm.tsx

- Line 6: `import { UnitSelect } from "@/components/forms/UnitSelect";`
- Line 336: `<UnitSelect value={values.unit} onChange={(unit) => updateField("unit", unit)}`

### frontend/src/features/samples/components/SampleForm.tsx

- Line 6: `import { UnitSelect } from "@/components/forms/UnitSelect";`
- Line 226: `<UnitSelect value={values.unit} onChange={(unit) => updateField("unit", unit)}`

### frontend/src/features/shipments/components/ShipmentDetail.tsx

- Line 7: `import { UnitSelect } from "@/components/forms/UnitSelect";`
- Line 228: `<UnitSelect value={weightUnit} onChange={v => setWeightUnit(v || "kg")} groups={["weight"]} ariaLabel={t("dispatchDialog.weightUnit")} /></label>`
- Line 285: `<UnitSelect value={weightUnit} onChange={v => setWeightUnit(v || "kg")} groups={["weight"]} ariaLabel={t("dispatchDialog.weightUnit")} /></label>`

### frontend/src/features/shipments/components/ShipmentForm.tsx

- Line 8: `import { UnitSelect } from "@/components/forms/UnitSelect";`
- Line 209: `<UnitSelect value={l.unit} onChange={v => setLine(i, "unit", v)} ariaLabel={t("lineFields.unit")} /></label>`
- Line 213: `<UnitSelect value={l.weight_unit} onChange={v => setLine(i, "weight_unit", v || "kg")} groups={["weight"]} ariaLabel={t("lineFields.weight_unit")} /></label>`

### frontend/src/features/waste-records/api.ts

- Line 36: `return apiClient<RunOption[]>('/production/runs?production_order_id=${orderId}');`

## Backend GET route source inventory

### backend/app/production/api/routes_dashboard.py

```python
# backend/app/production/api/routes_dashboard.py:14
@router.get("/dashboard", response_model=Dashboard,
            dependencies=[Depends(require_any_permission([P.ORDERS_READ, P.RESULTS_READ, P.DOWNTIME_READ, P.DEMANDS_READ]))])
def production_dashboard(period: Period = Query("3m"), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
```

### backend/app/production/api/routes_demands.py

```python
# backend/app/production/api/routes_demands.py:48
@router.get("/demand-lookups/customers", dependencies=[lookup_access])
def customers(search: str = Query(default="", max_length=255), svc=Depends(service)):
```

```python
# backend/app/production/api/routes_demands.py:53
@router.get("/demand-lookups/quotes", dependencies=[lookup_access])
def quotes(customer_id: UUID, svc=Depends(service)):
```

```python
# backend/app/production/api/routes_demands.py:59
@router.get("/demand-lookups/quotes/{quote_id}/items", response_model=list[CreateDemandItemRequest], dependencies=[Depends(require_any_permission([P.DEMANDS_CREATE, P.DEMANDS_UPDATE]))])
def quote_items(quote_id: UUID, customer_id: UUID, svc=Depends(service)):
```

```python
# backend/app/production/api/routes_demands.py:64
@router.get("/demand-lookups/sales-orders", response_model=list[SalesOrderLookup], dependencies=[lookup_access])
def sales_orders(customer_id: UUID, svc=Depends(service)):
```

```python
# backend/app/production/api/routes_demands.py:80
@router.get("/demands", response_model=PaginatedDemandList, dependencies=[allowed("read")])
def list_demands(filters: PlanningFilters = Depends(), statuses: list[ProductionDemandStatus] = Query(default=[]), svc=Depends(service)):
```

```python
# backend/app/production/api/routes_demands.py:86
@router.get("/demands/{demand_id}", response_model=DemandDetailResponse, dependencies=[allowed("read")])
def detail(demand_id: UUID, svc=Depends(service)):
```

```python
# backend/app/production/api/routes_demands.py:131
@router.get("/planning/demands", response_model=PaginatedPlanningList, dependencies=[Depends(require_permission(P.PLANNING_READ))])
def planning(filters: PlanningFilters = Depends(), statuses: list[ProductionDemandStatus] = Query(default=[]), svc=Depends(service)):
```

### backend/app/production/api/routes_downtime_events.py

```python
# backend/app/production/api/routes_downtime_events.py:44
@router.get("", response_model=list[DowntimeEventListItem], dependencies=[READ])
def list_downtime_events(filters: DowntimeFilters = Depends(), tenant: TenantContext = Depends(get_current_tenant),
```

```python
# backend/app/production/api/routes_downtime_events.py:54
@router.get("/summary", response_model=DowntimeSummaryRead, dependencies=[READ])
def downtime_summary(filters: DowntimeFilters = Depends(), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

```python
# backend/app/production/api/routes_downtime_events.py:60
@router.get("/{downtime_event_id}", response_model=DowntimeEventRead, dependencies=[READ])
def get_downtime_event(downtime_event_id: UUID, tenant: TenantContext = Depends(get_current_tenant),
```

### backend/app/production/api/routes_execution.py

```python
# backend/app/production/api/routes_execution.py:30
@router.get("/shift-rosters", dependencies=[Depends(require_permission(P.ROSTERS_READ))])
def list_rosters(shift_definition_id: UUID | None = None, workforce_member_id: UUID | None = None, date_from: date | None = None, date_to: date | None = None, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

```python
# backend/app/production/api/routes_execution.py:40
@router.get("/shift-rosters/{roster_id}", dependencies=[Depends(require_permission(P.ROSTERS_READ))])
def get_roster(roster_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

```python
# backend/app/production/api/routes_execution.py:65
@router.get("/runs", dependencies=[Depends(require_permission(P.RUNS_READ))])
def list_runs(production_order_id: UUID | None = None, workforce_member_id: UUID | None = None, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

```python
# backend/app/production/api/routes_execution.py:75
@router.get("/runs/{run_id}", dependencies=[Depends(require_permission(P.RUNS_READ))])
def get_run(run_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

### backend/app/production/api/routes_order_results.py

```python
# backend/app/production/api/routes_order_results.py:31
@router.get("/{production_order_id}/result", response_model=OrderResultRead, dependencies=[READ])
def get_order_result(production_order_id: UUID, tenant: TenantContext = Depends(get_current_tenant),
```

```python
# backend/app/production/api/routes_order_results.py:85
@overview_router.get("", response_model=list[ResultOverviewRow], dependencies=[READ])
def list_order_results(result_status: Literal["completed", "closed"] | None = Query(default=None, alias="status"),
```

### backend/app/production/api/routes_planning_orders.py

```python
# backend/app/production/api/routes_planning_orders.py:73
@router.get("/orders/{order_id}", response_model=PlanningOrderRead,
    dependencies=[Depends(require_permission(P.ORDERS_READ))])
def detail(order_id: UUID, db=Depends(get_db), tenant=Depends(get_current_tenant), customers=Depends(get_customer_lookup), can=Depends(permission_check)):
```

### backend/app/production/api/routes_production_orders.py

```python
# backend/app/production/api/routes_production_orders.py:46
@router.get("", response_model=list[ProductionOrderListItem],
    dependencies=[Depends(require_permission(P.ORDERS_READ))])
def list_production_orders(
```

```python
# backend/app/production/api/routes_production_orders.py:64
@router.get("/{production_order_id}", response_model=PlanningOrderRead,
    dependencies=[Depends(require_permission(P.ORDERS_READ))])
def get_production_order(
```

```python
# backend/app/production/api/routes_production_orders.py:118
@router.get("/{production_order_id}/status-history", response_model=list[StatusHistoryRead],
    dependencies=[Depends(require_permission(P.ORDERS_READ))])
def production_order_status_history(
```

### backend/app/production/api/routes_production_order_items.py

```python
# backend/app/production/api/routes_production_order_items.py:42
@router.get("", response_model=list[ProductionOrderItemListItem],
    dependencies=[Depends(require_permission(P.ORDERS_READ))])
def list_production_order_items(
```

```python
# backend/app/production/api/routes_production_order_items.py:56
@router.get("/{item_id}", response_model=ProductionOrderItemRead,
    dependencies=[Depends(require_permission(P.ORDERS_READ))])
def get_production_order_item(
```

### backend/app/production/api/routes_shift_definitions.py

```python
# backend/app/production/api/routes_shift_definitions.py:36
@router.get("", response_model=list[ShiftDefinitionListItem],
    dependencies=[Depends(require_permission(P.SHIFTS_READ))])
def list_shift_definitions(
```

```python
# backend/app/production/api/routes_shift_definitions.py:49
@router.get("/{shift_definition_id}", response_model=ShiftDefinitionRead,
    dependencies=[Depends(require_permission(P.SHIFTS_READ))])
def get_shift_definition(
```

```python
# backend/app/production/api/routes_shift_definitions.py:81
@router.get("/{shift_definition_id}/deletion-impact", response_model=ShiftDeletionImpact,
    dependencies=[Depends(require_permission(P.SHIFTS_READ))])
def get_shift_deletion_impact(
```

### backend/app/production/api/routes_waste_records.py

```python
# backend/app/production/api/routes_waste_records.py:43
@router.get("", response_model=list[WasteRecordListItem], dependencies=[READ])
def list_waste_records(
```

```python
# backend/app/production/api/routes_waste_records.py:63
@router.get("/summary", response_model=WasteSummaryRead, dependencies=[READ])
def order_waste_summary(production_order_id: UUID = Query(...), tenant: TenantContext = Depends(get_current_tenant),
```

```python
# backend/app/production/api/routes_waste_records.py:73
@router.get("/{waste_record_id}", response_model=WasteRecordRead, dependencies=[READ])
def get_waste_record(waste_record_id: UUID, tenant: TenantContext = Depends(get_current_tenant),
```

### backend/app/production/api/routes_work_centers.py

```python
# backend/app/production/api/routes_work_centers.py:36
@router.get("", response_model=list[WorkCenterListItem],
    dependencies=[Depends(require_permission(P.WORK_CENTERS_READ))])
def list_work_centers(
```

```python
# backend/app/production/api/routes_work_centers.py:46
@router.get("/{work_center_id}", response_model=WorkCenterRead,
    dependencies=[Depends(require_permission(P.WORK_CENTERS_READ))])
def get_work_center(
```

```python
# backend/app/production/api/routes_work_centers.py:60
@router.get("/{work_center_id}/delete-summary", response_model=WorkCenterDeleteSummary,
    dependencies=[Depends(require_permission(P.WORK_CENTERS_READ))])
def get_work_center_delete_summary(
```

### backend/app/quality/api/routes_certificates.py

```python
# backend/app/quality/api/routes_certificates.py:34
@router.get("/quality-settings", response_model=SettingsRead, dependencies=[Depends(require_permission(Q.COA_READ))])
def read_settings(tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

```python
# backend/app/quality/api/routes_certificates.py:50
@router.get(f"{PATH}/sources", response_model=CertificateSources, dependencies=[Depends(require_permission(Q.COA_CREATE))])
def certificate_sources(check_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

```python
# backend/app/quality/api/routes_certificates.py:59
@router.get(PATH, response_model=list[CertificateListItem], dependencies=[Depends(require_permission(Q.COA_READ))])
def list_certificates(status_filter: str | None = Query(default=None, alias="status", pattern="^(draft|issued|revoked)$"),
```

```python
# backend/app/quality/api/routes_certificates.py:81
@router.get(f"{PATH}/{{certificate_id}}", response_model=CertificateRead, dependencies=[Depends(require_permission(Q.COA_READ))])
def get_certificate(certificate_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
```

```python
# backend/app/quality/api/routes_certificates.py:135
@router.get(f"{PATH}/{{certificate_id}}/document.pdf", dependencies=[Depends(require_permission(Q.COA_READ))])
def certificate_document(certificate_id: UUID, lang: str = Query("en", pattern="^(ar|en)$"), current=Depends(get_current_user), db: Session = Depends(get_db)):
```

### backend/app/quality/api/routes_dashboard.py

```python
# backend/app/quality/api/routes_dashboard.py:13
@router.get("/dashboard", response_model=Dashboard,
            dependencies=[Depends(require_any_permission([Q.CHECKS_READ, Q.REJECTIONS_READ, Q.DEFECTS_READ, Q.NCR_READ, Q.COA_READ]))])
def quality_dashboard(period: Period = Query("3m"), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
```

### backend/app/quality/api/routes_incoming_inspections.py

```python
# backend/app/quality/api/routes_incoming_inspections.py:32
@router.get("/incoming/awaiting", response_model=list[AwaitingReceipt], dependencies=[Depends(require_permission(Q.CHECKS_READ))])
def awaiting_lots(q: str = Query(default="", max_length=60), include_done: bool = False, tenant: TenantContext = Depends(get_current_tenant),
```

### backend/app/quality/api/routes_ncr.py

```python
# backend/app/quality/api/routes_ncr.py:47
@router.get(PATH, response_model=list[NCRListItem], dependencies=[Depends(require_permission(Q.NCR_READ))])
def list_reports(status_filter: str | None = Query(default=None, alias="status", pattern=STATUSES), source_type: NCRSourceType | None = None,
```

```python
# backend/app/quality/api/routes_ncr.py:66
@router.get(f"{PATH}/lookups/users", response_model=list[UserOption],
            dependencies=[Depends(require_any_permission([Q.NCR_CREATE, Q.NCR_UPDATE]))])
def user_options(q: str = Query(default="", max_length=60), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

```python
# backend/app/quality/api/routes_ncr.py:73
@router.get(f"{PATH}/lookups/suppliers", response_model=list[SupplierOption],
            dependencies=[Depends(require_any_permission([Q.NCR_CREATE, Q.NCR_UPDATE]))])
def supplier_options(q: str = Query(default="", max_length=60), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

```python
# backend/app/quality/api/routes_ncr.py:80
@router.get(f"{PATH}/{{report_id}}", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_READ))])
def get_report(report_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
```

```python
# backend/app/quality/api/routes_ncr.py:92
@router.get(f"{PATH}/{{report_id}}/document.pdf", dependencies=[Depends(require_permission(Q.NCR_READ))])
def ncr_document(report_id: UUID, lang: str = Query("ar", pattern="^(ar|en)$"), current=Depends(get_current_user), db: Session = Depends(get_db)):
```

```python
# backend/app/quality/api/routes_ncr.py:188
@router.get("/ncr-actions/alerts", response_model=Alerts, dependencies=[Depends(require_any_permission([Q.NCR_ACTIONS_READ, Q.NCR_READ]))])
def alerts(tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
```

```python
# backend/app/quality/api/routes_ncr.py:194
@router.get("/ncr-actions", response_model=list[ActionRead], dependencies=[Depends(require_any_permission([Q.NCR_ACTIONS_READ, Q.NCR_READ]))])
def all_actions(status_filter: str | None = Query(default=None, alias="status", pattern="^(open|done|cancelled)$"), mine: bool = False,
```

```python
# backend/app/quality/api/routes_ncr.py:212
@router.get(f"{PATH}/{{report_id}}/attachments/{{attachment_id}}", dependencies=[Depends(require_permission(Q.NCR_READ))])
def attachment(report_id: UUID, attachment_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

### backend/app/quality/api/routes_quality_checks.py

```python
# backend/app/quality/api/routes_quality_checks.py:43
@router.get("", response_model=list[QualityCheckListItem], dependencies=[Depends(require_permission(Q.CHECKS_READ))])
def list_quality_checks(
```

```python
# backend/app/quality/api/routes_quality_checks.py:57
@router.get("/lookups/orders", response_model=list[InspectableOrder],
            dependencies=[Depends(require_any_permission([Q.CHECKS_CREATE, Q.REJECTIONS_CREATE]))])
def inspectable_orders(q: str = Query(default="", max_length=60), check_type: QualityCheckType | None = None,
```

```python
# backend/app/quality/api/routes_quality_checks.py:65
@router.get("/lookups/samples", response_model=list[SampleOption], dependencies=[Depends(require_permission(Q.CHECKS_CREATE))])
def inspectable_samples(q: str = Query(default="", max_length=60), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

```python
# backend/app/quality/api/routes_quality_checks.py:70
@router.get("/{check_id}", response_model=QualityCheckRead, dependencies=[Depends(require_permission(Q.CHECKS_READ))])
def get_quality_check(check_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
```

```python
# backend/app/quality/api/routes_quality_checks.py:122
@router.get("/{check_id}/specifications", response_model=list[PlanCandidate], dependencies=[Depends(require_permission(Q.CHECKS_MEASURE))])
def plan_candidates(check_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

### backend/app/quality/api/routes_quality_defects.py

```python
# backend/app/quality/api/routes_quality_defects.py:41
@router.get(
    "/quality-checks/{check_id}/defects",
    response_model=list[QualityDefectListItem], dependencies=[Depends(require_permission(Q.DEFECTS_READ))]
)
def list_quality_defects_by_check(
```

```python
# backend/app/quality/api/routes_quality_defects.py:57
@router.get("/quality-defects", response_model=list[QualityDefectListItem], dependencies=[Depends(require_permission(Q.DEFECTS_READ))])
def list_quality_defects(
```

```python
# backend/app/quality/api/routes_quality_defects.py:76
@router.get("/quality-defects/{defect_id}", response_model=QualityDefectRead, dependencies=[Depends(require_permission(Q.DEFECTS_READ))])
def get_quality_defect(
```

### backend/app/quality/api/routes_quality_rejections.py

```python
# backend/app/quality/api/routes_quality_rejections.py:41
@router.get("", response_model=list[QualityRejectionListItem], dependencies=[Depends(require_permission(Q.REJECTIONS_READ))])
def list_quality_rejections(
```

```python
# backend/app/quality/api/routes_quality_rejections.py:55
@router.get("/{rejection_id}", response_model=QualityRejectionRead, dependencies=[Depends(require_permission(Q.REJECTIONS_READ))])
def get_quality_rejection(rejection_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
```

### backend/app/quality/api/routes_return_inspections.py

```python
# backend/app/quality/api/routes_return_inspections.py:28
@router.get("/returns/awaiting", response_model=list[AwaitingReturn], dependencies=[Depends(require_permission(Q.CHECKS_READ))])
def awaiting_returns(q: str = Query(default="", max_length=60), include_done: bool = False, tenant: TenantContext = Depends(get_current_tenant),
```

```python
# backend/app/quality/api/routes_return_inspections.py:59
@router.get("/quality-checks/{check_id}/batch-shipments", response_model=list[BatchShipment], dependencies=[Depends(require_permission(Q.CHECKS_READ))])
def batch_shipments(check_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

### backend/app/quality/api/routes_specifications.py

```python
# backend/app/quality/api/routes_specifications.py:34
@router.get("/quality-test-parameters", response_model=list[ParameterRead],
            dependencies=[Depends(require_any_permission([Q.SPECS_READ, Q.CHECKS_MEASURE]))])
def list_parameters(active: bool = False, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

```python
# backend/app/quality/api/routes_specifications.py:65
@router.get("/quality-specifications", response_model=list[SpecificationListItem], dependencies=[Depends(require_permission(Q.SPECS_READ))])
def list_specifications(status_filter: str | None = Query(default=None, alias="status", pattern="^(draft|active|superseded)$"),
```

```python
# backend/app/quality/api/routes_specifications.py:86
@router.get("/quality-specifications/{spec_id}", response_model=SpecificationRead, dependencies=[Depends(require_permission(Q.SPECS_READ))])
def get_specification(spec_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
```

### backend/app/masterdata/api/routes.py

```python
# backend/app/masterdata/api/routes.py:33
@router.get("/products", response_model=list[ProductRead], dependencies=[Depends(require_permission(M.PRODUCTS_READ))])
def list_products(search: str | None = Query(default=None, max_length=60), kind: str | None = Query(default=None, pattern="^(finished|material)$"),
```

```python
# backend/app/masterdata/api/routes.py:41
@router.get("/products/legacy", response_model=list[LegacyValue],
            dependencies=[Depends(require_any_permission([M.PRODUCTS_CREATE, M.PRODUCTS_MAP_LEGACY]))])
def legacy_values(tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

```python
# backend/app/masterdata/api/routes.py:62
@router.get("/products/{product_id}", response_model=ProductRead, dependencies=[Depends(require_permission(M.PRODUCTS_READ))])
def get_product(product_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
```

```python
# backend/app/masterdata/api/routes.py:74
@router.get("/settings", response_model=SettingsRead, dependencies=[Depends(require_permission(M.SETTINGS_READ))])
def read_settings(tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

```python
# backend/app/masterdata/api/routes.py:86
@router.get("/lists", response_model=list[ListItemRead], dependencies=[Depends(require_permission(M.LISTS_READ))])
def list_items(list_name: ListName | None = Query(default=None, alias="list"), active_only: bool = False,
```

```python
# backend/app/masterdata/api/routes.py:111
@router.get("/lists/{list_name}/legacy", response_model=list[LegacyValue], dependencies=[Depends(require_permission(M.LISTS_MAP_LEGACY))])
def list_legacy(list_name: ListName, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
```

### backend/app/production/reporting/routes.py

```python
# backend/app/production/reporting/routes.py:16
@router.get('/production/production-orders/{order_id}/report.pdf',dependencies=[Depends(permission_checked_in_handler(P.REPORT_ORDER_FULL))])
def shortcut(order_id:UUID,lang:str='ar',orientation:str='portrait',sections:list[str]|None=Query(None),current=Depends(get_current_user),db:Session=Depends(get_db)):
```

```python
# backend/app/production/reporting/routes.py:20
@router.get('/reports/production/lookups/{kind}',dependencies=[Depends(permission_checked_in_handler(*P.REPORTS,*dict.fromkeys(LOOKUP_PERMISSION.values())))])
def lookups(kind:str,q:str=Query('',max_length=100),current=Depends(get_current_user),db:Session=Depends(get_db)):
```

### backend/app/quality/reporting/routes.py

```python
# backend/app/quality/reporting/routes.py:20
@router.get('/reports/quality/lookups/{kind}', dependencies=[Depends(permission_checked_in_handler(*R.ALL, *QUALITY_READS))])
def lookups(kind: str, q: str = Query('', max_length=100), current=Depends(get_current_user), db: Session = Depends(get_db)):
```

## Backend category / defect / operational reporting references

### backend/app/production/api/routes_waste_records.py

- Line 12: `from app.production.api.waste_schemas import WasteRecordCreate, WasteRecordListItem, WasteRecordRead, WasteRecordUpdate, WasteSummaryRead`
- Line 29: `return WasteRecordRead.model_validate(record).model_copy(update={"labels": service.labels([record], can)[record.id]})`
- Line 32: `@router.post("", response_model=WasteRecordRead, status_code=status.HTTP_201_CREATED, dependencies=[CREATE])`
- Line 33: `def create_waste_record(payload: WasteRecordCreate, tenant: TenantContext = Depends(get_current_tenant),`
- Line 43: `@router.get("", response_model=list[WasteRecordListItem], dependencies=[READ])`
- Line 48: `waste_category: WasteCategory | None = Query(default=None),`
- Line 57: `waste_category=waste_category, date_from=date_from, date_to=date_to)`
- Line 59: `return [WasteRecordListItem.model_validate(r).model_copy(update={"labels": labels[r.id]}) for r in records]`
- Line 73: `@router.get("/{waste_record_id}", response_model=WasteRecordRead, dependencies=[READ])`
- Line 83: `@router.patch("/{waste_record_id}", response_model=WasteRecordRead, dependencies=[UPDATE])`
- Line 84: `def update_waste_record(waste_record_id: UUID, payload: WasteRecordUpdate, tenant: TenantContext = Depends(get_current_tenant),`

### backend/app/production/api/waste_schemas.py

- Line 15: `class WasteRecordCreate(BaseModel):`
- Line 25: `waste_category: WasteCategory`
- Line 30: `class WasteRecordUpdate(BaseModel):`
- Line 39: `waste_category: WasteCategory | None = None`
- Line 45: `for field in ("waste_date", "quantity_wasted", "unit", "waste_category"):`
- Line 51: `class WasteRecordListItem(BaseModel):`
- Line 61: `waste_category: WasteCategory`
- Line 73: `class WasteRecordRead(WasteRecordListItem):`

### backend/app/production/application/allocation_service.py

- Line 12: `WasteRecord,`
- Line 93: `for name, model in (("downtime_events", DowntimeEvent), ("waste_records", WasteRecord)):`

### backend/app/production/application/services.py

- Line 36: `WasteRecord,`
- Line 153: `at_center = WasteRecord.work_center_id == work_center_id`
- Line 155: `at_center = at_center | WasteRecord.production_order_id.in_(order_ids)`
- Line 156: `if self.db.scalar(select(WasteRecord.id).where(WasteRecord.organization_id == tenant.organization_id, at_center).limit(1)):`

### backend/app/production/application/waste_service.py

- Line 1: `"""Operational waste records (PROD-WASTE-001): the only place that writes WasteRecord.`
- Line 19: `from app.production.infrastructure.models import ProductionOrder, ProductionOrderItem, WasteRecord, WorkCenter`
- Line 24: `"waste_category", "reason_code", "notes")`
- Line 44: `query = select(WasteRecord).where(WasteRecord.organization_id == self.org_id, WasteRecord.id == record_id)`
- Line 96: `record = WasteRecord(`
- Line 100: `waste_category=WasteCategory(data.waste_category).value, reason_code=data.reason_code, notes=data.notes,`
- Line 104: `self._audit("production_waste.created", order, record, category=record.waste_category, quantity=record.quantity_wasted, unit=record.unit)`
- Line 126: `record.waste_category = WasteCategory(values["waste_category"]).value`
- Line 142: `self._audit("production_waste.deleted", order, record, category=record.waste_category, quantity=record.quantity_wasted)`
- Line 154: `def list(self, production_order_id=None, production_run_id=None, work_center_id=None, waste_category=None, date_from=None, date_to=None):`
- Line 155: `query = select(WasteRecord).where(WasteRecord.organization_id == self.org_id)`
- Line 156: `for column, value in ((WasteRecord.production_order_id, production_order_id), (WasteRecord.production_run_id, production_run_id),`
- Line 157: `(WasteRecord.work_center_id, work_center_id),`
- Line 158: `(WasteRecord.waste_category, WasteCategory(waste_category).value if waste_category else None)):`
- Line 162: `query = query.where(WasteRecord.waste_date >= date_from)`
- Line 164: `query = query.where(WasteRecord.waste_date <= date_to)`
- Line 165: `return list(self.db.scalars(query.order_by(WasteRecord.waste_date.desc(), WasteRecord.created_at.desc())))`
- Line 198: `rows = self.db.execute(select(WasteRecord.waste_category, WasteRecord.unit, func.sum(WasteRecord.quantity_wasted), func.count()).where(`
- Line 199: `WasteRecord.organization_id == self.org_id, WasteRecord.production_order_id == order.id,`
- Line 200: `).group_by(WasteRecord.waste_category, WasteRecord.unit)).all()`

### backend/app/production/domain/permissions.py

- Line 64: `REPORT_SHIFT_WORKFORCE = "reports:production:shift_workforce"`

### backend/app/production/infrastructure/models.py

- Line 87: `waste_records: Mapped[list["WasteRecord"]] = relationship(`
- Line 88: `"WasteRecord",`
- Line 89: `foreign_keys="[WasteRecord.work_center_id]",`
- Line 341: `class WasteRecord(Base):`
- Line 351: `CheckConstraint("waste_category IN ('startup_setup','changeover','process','material_defect','machine_fault',"`
- Line 352: `"'handling_damage','contamination','other')", name="ck_waste_category"),`
- Line 396: `waste_category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)`

### backend/app/production/infrastructure/repositories.py

- Line 16: `WasteRecord,`
- Line 82: `select(func.count(WasteRecord.id)).where(`
- Line 83: `WasteRecord.work_center_id == work_center_id,`

### backend/app/production/reporting/builders.py

- Line 13: `ProductionOrderStatusHistory, ProductionResultEntry, WorkCenter, ShiftDefinition, WasteRecord, DowntimeEvent)`
- Line 206: `rows=scoped(db,WasteRecord,tenant,WasteRecord.production_order_id==order.id)`
- Line 208: `[(r.waste_date,label(r.waste_category,lang),r.quantity_wasted,r.unit,r.reason_code) for r in sorted(rows,key=lambda r:r.waste_date)],lang,`
- Line 360: `def shift_workforce(db,tenant,params,selected):`

### backend/app/production/reporting/definitions.py

- Line 19: `Section('waste','الهدر التشغيلي','Operational waste',available=b.has_data(b.WasteRecord,'production_order_id')),`
- Line 29: `('shift_workforce','الورديات والقوى العاملة','Shift workforce',WorkforceParams,(Section('rosters','تشكيلات الورديات','Shift rosters',requires_permission='workforce:members:read'),Section('participation','المشاركة الفعلية','Recorded participation',requires_permission='workforce:members:read',available=b.has_data(b.ProductionRunMember))),b.shift_workforce,'landscape',b.has_data(b.ShiftRoster))]:`

### backend/app/quality/api/inspection_schemas.py

- Line 208: `quality_defect_id: UUID | None = None`
- Line 257: `quality_defect_id: UUID | None`

### backend/app/quality/api/schemas.py

- Line 20: `defect_count: int = Field(default=1, gt=0)`
- Line 31: `defect_count: int | None = Field(default=None, gt=0)`
- Line 45: `defect_count: int`

### backend/app/quality/application/dashboard_service.py

- Line 94: `rows = self.db.execute(select(QualityDefect.defect_date, QualityDefect.defect_category, QualityDefect.defect_count)`

### backend/app/quality/application/rejection_service.py

- Line 97: `self._defect(data.quality_defect_id, check)`
- Line 102: `quality_defect_id=data.quality_defect_id, production_order_id=order.id, production_order_item_id=item.id if item else None,`

### backend/app/quality/domain/report_permissions.py

- Line 6: `'defects_analysis': ('Defects analysis', 'تحليل العيوب'),`

### backend/app/quality/infrastructure/models.py

- Line 198: `defect_count exists for defect-rate calculations:`
- Line 259: `defect_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)`
- Line 299: `At least one of quality_check_id or quality_defect_id should be present.`
- Line 328: `quality_defect_id: Mapped[uuid.UUID | None] = mapped_column(`

### backend/app/quality/reporting/builders.py

- Line 225: `[(d.defect_date, label(d.defect_category, lang), label(d.severity, lang), d.defect_count, d.description) for d in defects], lang))`
- Line 399: `def defects_analysis(db, tenant, params, selected):`
- Line 416: `cell['records'] += 1; cell['units'] += d.defect_count; cell[text(d.severity)] += d.defect_count`
- Line 440: `[(d.defect_date, code, orders.get(order_id, ('—',))[0], label(d.defect_category, lang), label(d.severity, lang), d.defect_count, d.description)`

### backend/app/quality/reporting/definitions.py

- Line 47: `('defects_analysis', 'تحليل العيوب', 'Defects analysis', DefectsParams,`
- Line 50: `b.defects_analysis, 'landscape', (Q.DEFECTS_READ,), ()),`

