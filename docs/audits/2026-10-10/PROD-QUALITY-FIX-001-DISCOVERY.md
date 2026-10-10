# PROD-QUALITY-FIX-001 — Phase 1 discovery and proposed design

Date: 2026-10-10. Status: **source review complete; live-data inventory unverified; implementation awaiting approval**.

This report examines the current working tree, including pre-existing uncommitted changes. It does not assume the repository matches HEAD or an earlier implementer's report. No application code, database records, migrations, dependencies, or commits were changed in this phase. Only this report and its evidence appendix were added.

The supplied task explicitly says: **“PHASE 1 — DISCOVERY (READ-ONLY, NO CODE CHANGES)”** and **“STOP and wait for approval.”** The design below is proposed, not implemented. The earlier readiness work is separate; this report makes no claim that it has finished.

## خلاصة القرار المقترح

1. فتح إضافة وفك التخصيص في المسودة والمعتمد وقيد التنفيذ والمعلّق، مع حماية معرّفات بنود الأمر. تغيير شرط الحالة وحده غير آمن.
2. استخدام مصدر الوحدات المركزي الحالي بالرمز، مع حفظ النص القديم وعدم تخمين الوحدات غير المعروفة.
3. توزيع كمية الهدر على بنود تصنيف؛ مجموع البنود يساوي كمية السجل، مع فصل إجماليات السجل عن إجماليات التصنيفات.
4. تحديد المقصود بسجل الجودة قبل التنفيذ: الفحص الحالي يدعم عدة عيوب بالفعل، والحقل الأحادي موجود في **سجل الرفض**. التوصية أدناه هي تعدد روابط العيوب في سجل الرفض مع الحفاظ على نموذج الفحص الحالي، وليست إنشاء نموذج QualityRecord جديد.
5. تعميم آلية Commercial للصفحات، واستبدال تحميل القوائم الكاملة في المحددات ببحث من الخادم. تقارير PDF لا تُبنى من الصفحة المعروضة.

ثلاثة اختلافات عن افتراضات المهمة تحتاج اعتمادًا ضمن التصميم: لا يوجد كتالوج عيوب له active، ولا جدول UOM له active، والتراجع إلى حقل تصنيف/عيب واحد لا يستطيع تمثيل كل العلاقات الجديدة دون أرشيف يحفظها.

## 1. Allocation after start

### Current guards and behavior

| Location | Verified behavior | Proposed treatment |
|---|---|---|
| `backend/app/production/application/planning_order_service.py:100` `_lock_draft_order` | Locks the tenant's order; rejects every state except DRAFT. Used by both add and quantity PATCH. | Introduce a shared allocation-state assertion; keep ordinary header editing separate. |
| Same file, `add_allocation:124` | Tenant mutex; duplicate ACTIVE demand-item rejection; demand remaining lock/check; matching product and unit. | Keep all checks, validate incoming specifications against existing lines with the compatibility checker too. |
| Same file, `change_allocation:147` | ACTIVE allocation required; DRAFT order required; excludes its own reservation while testing the new quantity. | Proposed: same allocation-open guard for quantity replacement, preserving the existing PATCH contract and audit. |
| Same file, `_validated:23` | Demand must be ready_for_planning or partially_planned; product required; quantity finite and positive; compatibility policy applied to requested set. | Preserve. One incoming item alone does not compare its spec with existing order lines; explicitly perform that comparison. |
| `application/allocation_service.py:97` `assert_releasable` | Blocks COMPLETED/CLOSED, IN_PROGRESS/ON_HOLD, and any started run, waste or downtime evidence. CANCELLED can pass if there is no evidence. | Public release must use the new locked/open sets, including rejection of CANCELLED. Remove execution-evidence blocking from allocation release. |
| Same file, `release_allocation:137` | ACTIVE required; rejects releasing the last allocation on a non-cancelled order; rebuilds lines; syncs demand; audit + commit. | Preserve last-allocation rule unless separately approved; preserve quantities and audit; replace destructive rebuild. |
| Same file, `release_all_for_cancellation` | Releases reservations before status is changed, using the same precondition. | Keep cancellation atomic; separate cancellation-specific preconditions from allocation eligibility. |
| `application/order_status_service.py:104` | Organization mutex then order FOR UPDATE, populate_existing, version check, permissions, transition preconditions, audit and commit. | Reuse; do not invent a parallel transition service. |
| `domain/order_lifecycle.py:39` | Cancel allowed only from DRAFT/RELEASED; complete only from IN_PROGRESS; no new status needed. | Preserve the state machine. Opening allocations in ON_HOLD does not authorize cancellation there. |
| `domain/order_lifecycle.py:53` | Existing OPEN set already contains exactly DRAFT, RELEASED, IN_PROGRESS, ON_HOLD for lateness. | Define named allocation-open/locked sets beside this state machine, referencing the existing set where appropriate, without duplicating literals. |
| `api/routes_planning_orders.py` | Add/PATCH use PLANNING_ALLOCATE; release uses PLANNING_RELEASE_ALLOCATION; creating a new order additionally requires ORDERS_CREATE. | Preserve PROD-RBAC-001 constants; eligible lookup should require allocation access, not order-creation access. |
| `planning_order_service.py:199` | `editable` is true only for DRAFT. | Keep it for header editing; add separate backend allocation actions. Do not broaden all order editing. |
| `frontend/.../production-orders/components/OrderLines.tsx:24` | Editing depends on `order.editable && canAllocate`; release also depends on this, unnecessarily requiring allocation permission. | Render add/change/release independently from backend actions and their permissions. |
| Same component, candidate effect | Reads planning page 1 with page_size=100, then filters product/unit/remaining locally. | Dedicated searchable eligible-demand lookup; no page-one-only selection. |
| `frontend/.../production-demands/planning-lifecycle.ts:7` | Release UI only allows draft/released. | Replace status duplication with backend allowed actions. |
| `frontend/.../production-demands/demand-allocations.tsx` | Release button uses that helper; allocate link also requires ORDERS_CREATE. | Separate “existing order” from “create order” permissions and choices. |
| `frontend/.../production-demands/planning-allocation.tsx` | Queue selection previews and creates a new production order. | Add existing-order path; no eligible-existing-order endpoint was found in the current routes. |

### Critical prerequisite: stable order-line identity

`backend/app/production/application/order_lines.py:10` currently clears every allocation's item reference, calls `order.items.clear()`, flushes, creates new lines, and relinks allocations. Its own comment says it runs only before execution exists.

That cannot be reused unchanged after start: WasteRecord and result entries have item references, and Quality keeps plain production item IDs across the module boundary. Rebuilding would risk FK failures or historical references pointing at removed items.

Proposed replacement, inside the existing service:

- Reconcile ACTIVE allocations against existing specification/unit groups. Update quantities in place for a matching line; append a line for a genuinely new specification. Never change IDs of existing executed lines.
- Preserve released allocation-to-line history. Keep a historical line at planned quantity zero when its allocations are released; do not delete a referenced line. Reuse its identity if the same specification is allocated again.
- Keep existing line numbers stable once execution has begun; append new numbers. Before execution, preserve existing presentation ordering where safe. Reports must tolerate zero-planned historical lines and zero denominators.
- Derive each line and header planned quantity from ACTIVE allocations, using the existing Decimal precision. Example 600 + 200 = 800. Preserve the current same-unit policy; do not add quantities in unlike units.
- Existing add endpoint can also address a manually created order. Do not let the first allocation silently replace manual planned lines. Proposed explicit guard: allocating to an existing order requires a planning-backed order; converting a manual order requires a separately designed operation. This eligibility restriction must be visible in the lookup/error message.
- Preserve `CUSTOMER_GOOD <= active allocated quantity`: additions, releases and quantity edits all lock at COMPLETED/CLOSED/CANCELLED. Results are writable only after completion. Locking prevents a stale add/release from slipping across complete.
- Traceability: nullable `order_status_at_allocation` code for old rows, mandatory from actual locked order for new rows; audit quantity edits with the status at edit time as well. Old rows remain “unknown” unless reconstructable from reliable history; never mark all historical allocations DRAFT by assumption. Badge/report column distinguishes IN_PROGRESS/ON_HOLD additions.

### Locking

`ProductionDemandRepository.lock_organization` uses the year-zero counter row as a tenant mutex. `AllocationService.validate_allocation` locks the tenant-joined demand item and calculates only ACTIVE reservations. Add locks order then demand item; release currently locks allocation then order, but tenant mutex serializes both. Status transitions use that same mutex then lock the order. Scheduler auto-start locks the order too.

Retain the mutex in this task; do not combine the UX change with removal of tenant serialization. Normalize lock order where touched: tenant mutex → order → allocation/demand items in stable order → aggregate/validate → mutate → commit. Revalidate remaining quantity after locks, never trust preview values. Test PostgreSQL competing allocation/complete and allocation/allocation operations, including both winning orders of execution.

## 2. Commercial pagination and endpoint inventory

### Exact existing pattern, not an assumed standard

- `backend/app/core/pagination.py`: `page` default 1, >=1; `page_size` default 50, 1..100; values above 100 rejected by request validation. Envelope **items, total, page, page_size, pages**; pages=0 for no matches. Count after authorization and filters; SQL offset/limit.
- `commercial/infrastructure/repositories.py:111`: customer ordering created_at DESC, id DESC; customer lookup orders name, id. Search/customer status/stage/owner/sector filters run in SQL. Samples/quotes/orders have their own domain filters and fixed sorting. Commercial does **not** expose one universal sort_by API; extending a common whitelisted sort contract must preserve existing fixed defaults.
- `commercial/api/routes_customers.py:81`: lookup search + explicit IDs + limit default20, capped100 for normal requests. Existing selected IDs can be hydrated without downloading every row. Reuse the concept and component behavior, not the customer endpoint for unrelated models.
- `frontend/src/lib/pagination.ts`: Page<T>, useListQuery, URL page/page_size/filter query, router.replace with scroll:false. Page sizes 25/50/100, default50. Changing filter or size resets page1. Add sort fields to this same hook rather than a separate state mechanism.
- `components/pagination/Pagination.tsx`, `ListToolbar.tsx`: shared controls. `customers-list-page.tsx` has loading/error/empty states, search debounce350ms, and redirects an out-of-range page to the last existing page. Its isMounted guard alone does not prevent an older in-flight request replacing a newer one; new usages should guard request identity/abort without duplicating the pagination mechanism.
- `production/api/demand_schemas.py`: demands/planning already paginate with default20, max100, sort_by/sort_order, but no `pages` field; retain `hidden_by_status` while aligning with core Page and default50. Queue business ordering is sequence, priority, delivery, created_at, id; do not replace it with commercial chronological sorting.

Paths below omit configured API prefix. P=/production; Q=/quality; M=/masterdata. “Page” means the shared envelope, not a fixed LIMIT. Row growth is inferred from the model/workflow, **not measured database counts**.

| GET endpoint / embedded collection | Current contract and growth | Proposed handling / consumers |
|---|---|---|
| P/demands | Page-like, default20, no pages; grows | Align; demands/list.tsx, demand edit/form lookups. |
| P/planning/demands | Same, sequence/filter metadata; grows | Align; demands/list.tsx, planning-allocation.tsx, OrderLines candidate picker must become lookup. |
| P/production-orders | Unpaged array; grows | Page; ProductionOrdersList plus waste/downtime filters/forms → separate searchable order lookup. |
| P/production-orders/{id}/items | Unpaged child list; grows with specifications | Page read-list if large; ProductionOrderItemsList. Full edit aggregate / selected item lookup must remain complete. |
| P/production-orders/{id}/status-history | Unpaged append-only array | Page; OrderStatusTimeline; reports query history independently. |
| P/orders/{id} and P/production-orders/{id}: lines/allocations | Embedded historical arrays | Separate paged read collections for growing history; preserve detail/edit aggregate semantics; OrderLines, order detail. |
| P/demands/{id}: item allocation history | Embedded arrays; grows across reallocations | Separate paged history, retain full computed summary; DemandAllocations. |
| P/runs | Unpaged array; grows | Page; ExecutionPanel; waste/downtime getOrderRuns become lookup with selected-ID hydration. |
| P/shift-rosters | Unpaged array; historical growth | Page; ExecutionPanel, ShiftDetail, workforce detail; roster selector becomes lookup. |
| Run/roster detail: members | Embedded team/history rows | Keep small team-edit aggregate; paginate a separate history view if unbounded; do not truncate team replacement payloads. |
| P/production-results | Unpaged completed/closed order overview | Page orders in DB first, then compute totals for those IDs; ResultsList. |
| P/production-orders/{id}/result | Complete entries + corrections + summaries | Keep authoritative full-order summary; page original entries separately with their correction groups; OrderResultSection, CloseResultDialog must never calculate from a page. |
| P/waste-records | Unpaged array | Page; WasteRecordsList; filter category via EXISTS. |
| P/waste-records/summary | Per-order grouped aggregate | No pagination; OrderWasteSection; totals computed over all filtered rows. |
| P/downtime-events | Unpaged array | Page; DowntimeEventsList; filter controls use lookup. |
| P/downtime-events/summary | Aggregate | No pagination; list/OrderDowntimeSection. |
| P/work-centers | Small tenant reference, unpaged | Keep small selector contract. Page management if growth warrants; use lookup for large tenants. See exact multi-module consumers in appendix. |
| P/shift-definitions | Small shift-template reference, unpaged | Keep small selector contract; ShiftsList and ExecutionPanel. Rosters, not templates, are the growing history. |
| P/demand-lookups/customers | Search list | Keep lookup, explicitly bound limit + selected IDs; demand form. |
| P/demand-lookups/quotes | All quotes of customer via provider | Search/limit lookup; demand form; keep referenced historical quote display. |
| P/demand-lookups/quotes/{id}/items | One document's lines | Keep document aggregate, not a paged selector. |
| P/demand-lookups/sales-orders | Confirmed customer orders and source lines | Search bounded order lookup + selected order detail; from-sales-order.tsx; never silently discard available source lines. |
| Q/quality-checks | Array, service limit200; silently capped | Page; QualityChecksList, OrderQualitySection. |
| Q/quality-checks/{id}/defects | Unpaged occurrence array | Page display; QualityDefectsList; separate lookup for new rejection picker. |
| Q/quality-defects | Unpaged array with category/severity/order/date filters | Page; no direct frontend list call found; retain API coverage for external callers. |
| Q/quality-rejections | Array, service limit200 | Page; QualityRejectionsList, OrderQualitySection. |
| Q/non-conformance-reports | Array, limit500 | Page; NcrReportsList. |
| Q/ncr-actions | Array, limit500 | Page; CorrectiveActionsList; retain overdue/owner filters. |
| Q/ncr-actions/alerts | Counts + bounded attention data | Keep dashboard summary, not a Page. use-capa-alerts.ts. |
| Q/quality-specifications | Array, limit500 | Page; SpecificationsList; plan selection uses its dedicated candidates query. |
| Q/quality-test-parameters | Unpaged tenant-managed catalogue | Page management if growing; keep small reference selection or searchable lookup; TestParametersPage, SpecificationForm. |
| Q/quality-certificates | Array, limit500 | Page; CertificatesList, CheckCertificatesSection. |
| Q/quality-certificates/sources | One check's eligibility + customer options | Keep aggregate; CheckCertificatesSection. |
| Q/quality-checks/lookups/orders, /lookups/samples | Search lookup, bounded in support service | Keep lookup; QualityCheckForm and QualityRejectionForm; align query/limit and selected-ID handling. |
| Q/quality-checks/{id}/specifications | Candidate plan references | Keep searchable small selection; MeasurementsSection; never use paginated specs page1 as candidate source. |
| Q/returns/awaiting | Search, bounded awaiting-return list | Page operational queue; QualityReturnsList; preserve source ownership validations. |
| Q/incoming/awaiting | Search, bounded awaiting-lot list | Page operational queue; IncomingInspection. |
| Q/quality-checks/{id}/batch-shipments | Linked shipment list | Growing containment view: paged read list; ReturnInspection; containment logic must query entire set independently. |
| Q/non-conformance-reports/lookups/users, /lookups/suppliers | Search + limit50 | Keep lookup; NcrReportForm/Detail. |
| Quality check/NCR details: measurements, rejections, items, actions, attachments, history | Embedded record aggregates | Preserve command/detail payloads; add separate pages for unbounded history/actions; do not silently page a certificate snapshot or form's editable lines. |
| M/products | Array, limit500 | Page Products management; introduce search + selected-key product lookup/detail. Update catalog.ts and all consumers before changing envelope. |
| M/products/legacy | Distinct legacy values/counts | Potentially growing remediation list: Page; Products legacy mapping view. |
| M/lists | Small reference lists, configured max500 per list | Keep small selectors; split management paging only if needed; ReferenceLists, ListSelect, catalog hooks. |
| M/lists/{list_name}/legacy | Distinct unmapped values/counts | Page remediation view; ReferenceLists. |
| P/dashboard, Q/dashboard | Aggregates/bounded attention | No pagination of KPI responses; never base counts on list page length. |
| /reports/production/lookups/{kind}, /reports/quality/lookups/{kind} | Search lookups, limit100 | Keep report selectors; ReportForm uses reports API, not operational list endpoints. |

See **CONSUMER-EVIDENCE.md** for exact API function references, direct HTTP consumers, and backend consumer locations. Static inventory covers this workspace; external clients cannot be enumerated from repository code. If such clients exist, announce the envelope change/version contract; do not claim they were updated.

### Pagination architecture and proposed indexes

Reuse core Page/page_params/paginate/page_of. Every count, data query and lookup includes organization and applicable authorization scope. Sort fields must be whitelisted; append unique id. Use EXISTS for category/defect filters so a parent appears and is counted once. Use selectin/batched fetching for child values on a page.

Existing indexes include waste(org,order), downtime(org,center,start), demand(org,status/customer/sequence), allocation(org,item,status), allocation(org,order), result(org,order), and status-history(org,order,created_at). Most other fields have only individual indexes. Proposed additions, subject to duplicate/live-schema check before migration:

| Query | Candidate composite index | Purpose |
|---|---|---|
| Waste chronological page | (organization_id, waste_date, created_at, id) | tenant/date list sort |
| Waste category EXISTS | child(organization_id, category, waste_record_id) | category lookup without duplicate parent rows |
| Downtime page | (organization_id, start_time, id) | list independent of center; existing center index retained |
| Orders/results overview | (organization_id, status, created_at, id) | state-filtered order paging |
| Runs | (organization_id, production_order_id, created_at, id) | order execution list |
| Rosters | (organization_id, effective_from, id) | roster history; optional shift-specific variant only if query needs it |
| Checks | (organization_id, check_datetime, id) | chronological inspection list |
| Defects | (organization_id, quality_check_id, defect_date, id) | per-check defect paging |
| Rejections | (organization_id, rejection_date, created_at, id) | rejection list |
| Proposed rejection-defect links | (organization_id, defect_id, quality_rejection_id) | EXISTS filter |
| NCR/actions | NCR(org,report_date,created_at,id); action(org,status,due_date,id) | report/overdue lists |
| Certificates | (organization_id, created_at, id) | certificate chronology |
| Products | (organization_id, active, name_ar, id) | deterministic existing default order |
| Specifications | existing unique(org,code,revision) assessed first | avoid redundant index; add id tiebreaker to query |

A leading-wildcard ILIKE is not solved by a normal B-tree. Do not introduce a trigram extension merely to claim search is indexed; measure realistic data/explain after implementation. Indexes are proposed, not applied or performance-tested.

## 3. Waste unit from central UOM

### Verified current model

- Actual table **production_waste_records**, model `WasteRecord` in production/infrastructure/models.py:343. `quantity_wasted Numeric(15,3)`, `unit String(32) NOT NULL`. API only strips/limits text; waste_service writes it without checking central units.
- `backend/app/core/units.py` is the global central code dictionary UNITS, with names, symbols and weight conversions. There is no unit ORM table, org scope, active flag, or units endpoint. Master Data product/default/property units validate against this dictionary (`masterdata/api/schemas.py:23`).
- Frontend mirrors codes in `frontend/src/lib/units.ts`; existing quote-unit tests check parity. Reuse `components/forms/UnitSelect.tsx`, whose existing behavior deliberately retains selectable legacy free text. For waste editing, an opt-in strict mode is needed so a legacy value displays but cannot be resaved as a valid new selection. Do not change legacy behavior in unrelated forms.
- PROD-OUTPUT-001 `ProductionResultEntry.unit` is also String(32); `result_service._validated:142` derives it from order item/order and rejects mismatch. It **does not validate membership in UNITS**, and secondary unit remains a separate field. This distinction matters: “same as results” means code storage, not evidence that results already have active-UOM validation.

### Live distinct values/counts: NOT VERIFIED

The current environment could not run the configured Python interpreter. `py -0p` returned “No Installed Pythons Found!”. Attempting the PostgreSQL18 psql executable via Node returned ENOENT. No SQL reached the database; no connection credentials were printed. The apparent tool directories/old venv configuration are not proof of runnable tools.

Required read-only query before migration, using the actual table name:

```sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = 5000;
SELECT unit, count(*) AS record_count
FROM production_waste_records
GROUP BY unit ORDER BY record_count DESC, unit;
SELECT waste_category, count(*) AS record_count
FROM production_waste_records GROUP BY waste_category;
ROLLBACK;
```

No stored values or counts are fabricated here. All mapping examples below are proposed mappings, not observations of live data. Run the inventory under authorized operational access and also per organization when reconciling; expose no tenant-wide data through application endpoints.

### Proposed migration and validation

Keep standard string code (no production-local enum/catalogue). Validator in core unit utilities: existence in central UNITS; all currently defined codes are globally available. “Inactive” cannot be enforced against nonexistent metadata. Recommended minimum design treats membership as availability; if independently deactivatable units are mandatory, add that metadata centrally as an explicitly approved extension, not a Waste-only flag.

Add `legacy_unit_text` (exact original text) and `unit_needs_review`. Preserve original text for every transformed row, not just unknown rows, to support downgrade. Standard known code remains unit; unmapped row has nullable unit and original text with needs_review=true. Avoid sentinel fake units. Read/API/report schemas must represent that legacy state; UI requires choosing a valid unit on its next edit.

Explicit frozen migration mapping includes exact canonical codes plus reviewed aliases such as kg/KG/كجم/كيلو → kg. No fuzzy matching, unit conversion, default-to-kg, or guessed quantity changes. Unknown values must not be grouped under a false shared unit in summaries: show their original text and review status, separately from verified canonical totals.

Migration reports mapped counts by original/code, unmapped values with counts, and reconciliation total. Downgrade restores original legacy text where retained and canonical code for post-migration rows. Do not silently discard metadata required to reconstruct review decisions; preserve an archival snapshot if downgrade is used after new edits.

Consumers: waste schemas/service/routes/types/form/detail/list/summary, UnitSelect optional strict behavior, production order report waste table, central localized formatting, Arabic/English review hint, migration/regression tests. No inventory, shipping or result quantity semantics change.

## 4. Multiple waste categories

Current WasteCategory is a domain Enum of eight string values: startup_setup, changeover, process, material_defect, machine_fault, handling_damage, contamination, other. Storage is a single `waste_category` string with CHECK constraint, not a reference FK. API create requires it; PATCH rejects null; frontend uses one selector and one badge.

Current consumers:

- `production/application/waste_service.py` create/update audit, list equality filter, summary grouping by category/unit.
- `production/api/waste_schemas.py`, `routes_waste_records.py`, infrastructure/models.py and domain/enums.py.
- `production/reporting/builders.py:205` order-full waste section reads `r.waste_category` and record quantity; definitions enables the section when records exist.
- `frontend/src/features/waste-records/{types.ts,api.ts,waste-rules.ts}` and all components: WasteRecordForm, WasteRecordsList, WasteRecordDetail, WasteCategoryBadge, OrderWasteSection.
- Production allocation execution-evidence/work-center deletion guards reference WasteRecord existence only; no category calculation there. Keep those semantics apart from the changed public allocation-release rule.
- Existing production dashboard has no WasteRecord/category calculation. Existing `shift_workforce` report lists rosters/members, not waste; no separate ShiftReport waste computation was found in these modules. Do not invent a category consumer or add unrelated dashboard metrics. Any future category metric must use line quantities.

Proposed child table `production_waste_record_categories`: id, organization_id, waste_record_id, category code, quantity Numeric(15,3), created_at, updated_at. Unique(record,category), CHECK(quantity>0), category CHECK, FK to parent. Follow the explicit association-row conventions of ShiftRosterMember/ProductionRunMember; enforce org alignment in service and, where practical, composite parent tenant FK.

API accepts `categories: [{category, quantity}]`. One category may omit its quantity; server assigns full quantity_wasted. Multiple categories require explicit positive finite quantities and exact Decimal sum = record.quantity_wasted. Duplicate/unknown category rejected; empty array rejected. All lines inherit record unit; no per-line unit. PATCH changing record quantity must reconcile categories in the same locked transaction, not leave old split totals.

Category filter uses EXISTS scoped to organization. Record summary sums record quantities once and counts record IDs once. Category summary sums child quantities, grouped by category **and unit**. Separate queries avoid join multiplication; no category count summation used as record count. Reports show a single waste record with category quantities nested/readable, or one row per category clearly excluding repeated header quantity from totals.

Migration: validate legacy quantities/categories; backfill one line with full quantity per record; reconcile parent/child counts and sums by unit; only then remove old column/constraint. Fail and report anomalies instead of deleting rows or manufacturing quantities.

Downgrade: largest-quantity category, deterministic category-code tiebreaker. This produces a usable old schema, but is inherently lossy for new multi-category records. To meet “no data loss”, archive **all** child rows before removal and retain that archive through downgrade; next upgrade restores it only after validating consistency with any edits made while downgraded. Alternatively retain the old column through an expand/contract compatibility period. Approval must acknowledge this storage requirement; a naked drop-table is not a lossless downgrade.

Frontend reuses current form/styles and enum labels; multi-checkbox/select UI and quantities with exact thousandth arithmetic, live remaining, one category autofill, chips, full detail. Existing selectors are predominantly native select; no general searchable multi-select was identified. Add one reusable accessible component only if the quality use-case needs it, not one per screen.

## 5. Multiple quality defects — task/model mismatch

### Actual domain

- No class/table named QualityRecord or reusable Defect catalogue was found.
- `QualityCheck` is the inspection header. `QualityDefect` is an **occurrence belonging to a required quality_check_id**, with org ID, defect_category enum, severity enum, defect_count, description, actor and timestamps. It has no active flag and is not global/reference data.
- A check already has multiple occurrences via GET/POST `/quality-checks/{id}/defects`. QualityDefectsList displays them and QualityDefectForm adds a row. No single defect column on QualityCheck needs migrating.
- **QualityRejection.quality_defect_id** is the nullable single FK (`models.py:328`). Rejection service validates same organization and, if a check is supplied, the same check. The frontend rejection form currently does not provide a full multi-defect selection flow.
- There is no existing Quality-specific defect M2M to reuse. QualitySpecificationLine has a unique specification/parameter pair; NCR items/actions are explicit child entities. Foundation RolePermission and Production roster membership provide association-row conventions.

### Decision, severity and analysis behavior

- `check_service.close` creates a pending rejection from rejected quantity in the same transaction. It does not require a defect row or choose one; it derives quantities from the close decision, not defect counts/severity.
- `QualityRejectionCreate.quality_defect_id` is optional. “At least one if currently required” does not justify suddenly rejecting existing manual/auto-created rejections without defects.
- No automatic highest-defect-severity on the check/rejection was found. Severity is on each occurrence; NCR severity is its own field, manually/default populated. Do not overwrite NCR severity because a defect link was changed.
- Disposition remains the existing decide/execute flow and permissions. Linking several defects must not cause several automatic rejections for the same rejected quantity or change the close guard.
- `quality/reporting/builders.py:399` currently aggregates `defect_count` into “units”, including Pareto and severity groups; it also counts rows separately. `quality/application/dashboard_service.py:93` sums defect_count. These cannot be described as distinct defective product units when defects overlap. Occurrence count must have an explicit definition and consistent labels.
- List filters use category/severity on QualityDefect. Check report lists defect rows; order report's Quality sections, quality reports, dashboards, rejection lists/detail and potential COA presentation all need regression review. Certificates' frozen measured results must remain frozen and not be recomputed from new links.

### Recommended adaptation requiring approval

Keep QualityCheck → QualityDefect occurrence model. Add **QualityRejectionDefect** with id, organization_id, quality_rejection_id, defect_id, optional affected_quantity, timestamps, unique(rejection,defect). This addresses the actual single-FK limitation without a parallel QualityRecord module.

- Only same-org occurrences; where rejection references a check, every selected occurrence must belong to it. A manual rejection's occurrences must also match its production context; matching org alone is insufficient.
- Optional affected quantity must be finite and positive when provided, bounded by the applicable rejected/inspected quantity once the chosen context is resolved. Overlap is permitted; never sum across defects as record or rejected total.
- Expose computed linked severity with explicit rank minor < major < critical. No lexical MAX. Empty set yields null; it does not invent minor. Freeze/report history policy must be explicit if editing an occurrence after rejection decision is permitted.
- Occurrence Pareto counts distinct QualityDefect IDs, not the number of rejection links (the same occurrence may be referenced twice). Keep historical defect_count as separate legacy frequency information; do not erase it or silently relabel it as affected quantity. Any changed dashboard metric label must communicate the changed measure.
- No active-defect validation is possible against current occurrence schema. Recommended: validate occurrence/context eligibility; preserve historical display. If the intended UI instead selects reusable named defect definitions with active/inactive, that requires a **central definition catalogue and different migration design**, not merely an M2M join to occurrences. That alternative is not assumed approved.
- Frontend: searchable selection of existing occurrences in the permitted check/context; remove before save; optional quantities; chips/+N and full detail/report. If the requested screen is actually “add several defect categories during inspection”, enhance the existing child-row form/batch service instead; no duplicate check-defect join table is necessary.

Migration for the recommended adaptation: each non-null rejection.quality_defect_id becomes one link; null stays no links, affected_quantity stays null because no legacy field establishes it. Validate cross-org/check/context anomalies and report them before cutover. Remove the old FK column only after every consumer is updated. Downgrade picks highest severity, stable created_at/id tie, preserving other links in an archive as for waste. Do not migrate every QualityDefect into a shared catalogue or invent active flags without approval.

Consumers to update if approved: quality infrastructure models/repositories, rejection_service, inspection_schemas, routes_quality_rejections, defects lookup/context validation, quality-check/rejection/detail views, reporting/builders and relevant definitions/schemas, dashboard_service metrics, frontend quality-rejections API/types/forms/lists/detail, quality-defects/check detail integration, Arabic/English labels. NCR/certificate business decisions remain owned by their existing services.

## 6. Migration/release sequence and validation gate

After approval, implement in requested order **1 → 3 → 4 → 5 → 2**, one focused commit per item. Existing unrelated dirty files must not be swept into these commits. Check current Alembic heads at implementation time; never invent revision ancestry from filenames/dates.

1. Allocation constant/actions, non-destructive line reconciliation, trace column, eligible lookup and frontend; PostgreSQL concurrency regression.
2. Unit legacy inventory first; reviewed frozen mapping migration; backend canonical validation; strict waste selector; preserve old text.
3. Category child table/backfill/checks; every API/report/filter/UI consumer; downgrade archival strategy.
4. Only the approved Quality interpretation; migration of the actual old field; explicit severity/occurrence semantics.
5. Core pagination reused across inventory; lookup conversions shipped together; indexes justified per query; pages cannot change totals.

Migration scripts run transactionally on PostgreSQL. Backfill keyed by parent/category or parent/defect avoids duplicate relation rows; do not mark a failed/partial migration successful. Upgrade → downgrade → upgrade tests must compare row counts, exact old text, quantities, links and archives, including post-upgrade multi-line data. A schema downgrade selecting one value is not evidence that all values survived.

### Required behavior tests (not executed in Phase 1)

| Task test IDs | Implementation gate / existing suites to extend |
|---|---|
| 1–8 allocation | `backend/tests/test_production_allocation.py`, `test_production_allocation_lifecycle.py`, `test_production_order_lines.py`, `test_production_order_status.py`, `test_production_allocation_postgres.py`; all open/locked states, independent permissions, totals, same org, stale preview, stable line IDs and surviving Quality/Waste links, both concurrency outcomes. |
| 9–10 units | `backend/tests/production/test_waste_records.py`, `test_waste_migration_postgres.py`; canonical/unknown/alias data, exact original text, review-on-edit; active policy only after model decision. |
| 11–16 category quantities | Same waste suites + `production/test_production_reports.py`; exact Decimal totals, duplicate/nonpositive/empty split, single autofill, EXISTS with two matches, category vs record counts, unlike units kept separate, downgrade archive. |
| 17–21 defects | `quality/test_quality_defects.py`, `test_quality_inspections.py`, `test_quality_reports.py`; approved target, tenant/context checks, severity ranking, overlapping quantities, legacy-null associations, occurrence metrics and no duplicated rejection totals. |
| 22–25 pagination | `commercial/test_list_pages.py` as contract precedent; add module list tests for page2/ties/cap/filter/sort/scoped totals and search-selected-ID beyond page1. Existing frontend `components/customers-pagination.test.tsx` as behavior precedent. |
| 26 regression | `test_all_route_authorization.py`, `production/test_production_rbac.py`, `test_module_boundaries.py`, reporting suites, execution foundation, incoming/return inspection, NCR, certificates and frontend waste/quality components. |

Proposed commands after implementation and restoration of the Python toolchain:

```powershell
python -m pytest tests/test_production_allocation.py tests/test_production_allocation_lifecycle.py tests/test_production_order_lines.py tests/test_production_order_status.py tests/production tests/quality tests/test_all_route_authorization.py tests/test_module_boundaries.py -q
# PostgreSQL test jobs use isolated schemas and RUN_POSTGRES_TESTS=1 as required by existing fixtures.
python -m pytest tests/test_production_allocation_postgres.py tests/test_waste_migration_postgres.py -q
# From frontend (scripts verified in package.json):
npm test
npm run i18n:check
npx tsc --noEmit
npm run build
```

These are planned commands, not passing results. No 26-test completion claim is made.

## 7. Actual checks and outstanding items

Performed: source searches of all target API modules, service/ORM/domain references, repository-wide waste/defect consumers, frontend API exported-name references and direct URL consumers, existing pagination implementation and ADR, migration/test-file inventory, runtime availability probes. Exact reference evidence is in the companion appendix. No browser/UI runtime session was claimed.

Actual tool output:

```text
Configured Python interpreter invocation: CommandNotFoundException
py -0p: No Installed Pythons Found!
Read-only psql probe via Node: PROBE_UNAVAILABLE ENOENT exit null
```

**NOT IMPLEMENTED — by the explicit Phase 1 approval gate:** all five application fixes, frontend changes, migrations, new tests and commits.

**NOT VERIFIED — environment limitation:** live distinct waste units/counts, live schema/index drift, current migration head in the running database, runtime test/build results. The unit inventory must be completed before mapping/cutover; static test fixtures cannot substitute for it.

### Approval needed

Approve this concrete Phase 2 design, including stable order lines, global canonical UOM membership, downgrade archives, and the proposed **QualityRejectionDefect** adaptation? If “QualityRecord” means the inspection-entry form instead of rejection, select that target before implementation; existing checks already support multiple defect rows. Reusable active/inactive defect definitions would be a separate catalogue design, not an existing feature.
