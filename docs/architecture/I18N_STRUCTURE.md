# بنية الترجمة — المرحلة 2أ

## مكان كل نوع من النصوص

نصوص الواجهة، مثل عنوان صفحة العملاء ورسائل التحقق، تبقى في ملفات JSON متعددة حسب الوحدة داخل `frontend/src/i18n/locales/{ar,en}/`. أما أسماء البيانات التي يدخلها المستخدم فتظل في قاعدة البيانات: `name_ar` و`name_en` حيث يدعمهما النموذج. الاسم أو العنوان أو الملاحظة المدخلة بلغة واحدة تُعرض كما حُفظت ولا تُترجم آليًا.

الثوابت المخزنة كمفاتيح، مثل `shipping.status.draft` وأسباب المرتجعات، لها مصدر ترجمة واحد في `shared/i18n/{ar,en}/enums.json`. تُجمع تحت الوحدة ثم نوع الحقل. تقرأ الواجهة هذا المصدر، ويتوفر قارئ للخادم لاستخدامه لاحقًا في المستندات المطبوعة. لا تُنسخ ملفات المصدر يدويًا إلى مجلدي التطبيقين.

## القواعد المعتمدة

1. نصوص الواجهة في ملفات JSON متعددة، ملف لكل وحدة.
2. البيانات الثنائية اللغة في قاعدة البيانات بعموديها، والبيانات ذات اللغة الواحدة تُعرض كما هي. اختيار لغة العرض له مساعد واحد مع بديل من الاسم الآخر الموجود فقط.
3. جميع القيم الثابتة المخزنة كمفاتيح تستخدم مصدر الترجمة المشترك، دون قوائم ترجمة مكررة في اللوحات أو ملفات الوحدات.
4. الخادم لا يرسل أسماء معروضة مشتقة من مفاتيح ثابتة للشاشات؛ يرسل المفاتيح ونوعها. أسماء البيانات الفعلية، مثل اسم مركز العمل، تبقى نصًا كما أدخله المستخدم.
5. لا يُعرض مفتاح خام ولا بديل إنجليزي تلقائي. غياب الترجمة خطأ واضح في التطوير والاختبار، وفي الإنتاج يظهر «—» مع تحذير خالٍ من بيانات المستخدم.

## البناء والتشغيل

تبقى سياقات بناء صورتي التطبيقين محصورة في `backend/` و`frontend/`. يصل `shared/` كسياق إضافي مسمى `shared`، ويُنسخ عبر `COPY --from=shared` في Dockerfile. تستخدم أوامر Docker في CI الخيار `--build-context shared=./shared` (المكافئ لـ `build-contexts` في إجراء البناء)، وتستخدم Compose الخاصية `additional_contexts`. القارئ المحلي يصل إلى المصدر نفسه من جذر المستودع؛ لا توجد نسخة ثانية متتبعة في Git. يجب أن يشمل تتبع ملفات Next المستقلة المصدر المشترك داخل الصورة النهائية.

## العقود والبيانات الديناميكية

تستخدم breakdown وranking مفاتيح القيم الثابتة دون `label` مشتق منها. المدينة تُحل من قائمة المدن، والمنتج من كتالوج المنتجات، واسم مركز العمل نص ذو لغة واحدة. تفاصيل attention تحمل نوع القيمة مثل `downtime_category` أو حالة الفحص ليختار العميل قاموسها. أسماء العملاء المنسوخة لا تُغيّر في قاعدة البيانات: عند وجود معرف يُستخدم الاسم الحالي بلغته، وإلا يُعرض النص المحفوظ. أسماء الصلاحيات تُحل من كود الصلاحية.

## خطة المرحلتين التاليتين — ملفات فقط، دون تنفيذ

### 2ب

- `frontend/src/i18n/locales/{ar,en}/*.json`
- `frontend/src/features/**`
- `frontend/src/components/**`
- `frontend/scripts/check-i18n.mjs`

### 2ج

- `backend/app/*/reporting/document.py`
- `backend/app/*/reporting/return_document.py`
- `backend/app/*/reporting/locales/{ar,en}/*.json`
- `backend/app/*/reporting/templates/*.html`
- `backend/tests/*/test_*document*.py`

## جدول مصادر الثوابت

يورد الجدول التالي تعريفات enum وثوابت domain من الكود نفسه؛ القيم المرجعية الديناميكية مثل المدن والمنتجات مصدرها بيانات masterdata وليست ثوابت مترجمة في هذا القاموس. لا تشمل إعدادات المهلة والأوزان وحدود الحساب أنواعًا معروضة للمستخدم.

| الوحدة | المصدر | التعريفات |
|---|---|---|
| commercial | `backend/app/commercial/domain/action_permissions.py` | EXTRA_ACTIONS? SAMPLE_STATUS_PERMISSIONS |
| commercial | `backend/app/commercial/domain/complaint_wording.py` | WORDS? ACTIONS |
| commercial | `backend/app/commercial/domain/complaints.py` | STATUSES? ACTIONS? PERMISSIONS? CATEGORIES? DEPARTMENTS |
| commercial | `backend/app/commercial/domain/enums.py` | CustomerStatus: 'active', 'inactive', 'on_hold', 'archived', 'blacklisted'? RelationshipStage: 'lead', 'contacted', 'qualified', 'prospect', 'negotiating', 'trial_customer', 'active_customer', 'repeat_customer', 'strategic_customer'? PriorityLevel: 'low', 'medium', 'high'? InteractionType: 'call', 'visit', 'whatsapp', 'email', 'meeting'? FollowUpStatus: 'pending', 'in_progress', 'completed', 'cancelled'? FollowUpPriority: 'low', 'medium', 'high', 'urgent'? SampleStatus: 'requested', 'in_preparation', 'delivered', 'evaluated', 'cancelled'? SampleDecision: 'pending', 'accepted', 'rejected'? SampleEvaluationResultStatus: 'accepted', 'rejected', 'needs_modification'? SampleEvaluationNextAction: 'proceed_to_quote', 'revise_sample', 'close_request', 'further_review'? QuoteStatus: 'draft', 'issued', 'accepted', 'rejected', 'expired'? CommercialOrderStatus: 'draft', 'confirmed', 'cancelled', 'converted_to_production' |
| commercial | `backend/app/commercial/domain/lifecycle.py` | QUOTE_TRANSITIONS? QUOTE_NEEDS_REASON? ORDER_TRANSITIONS |
| commercial | `backend/app/commercial/domain/pricing.py` | HALALA? UNIT_PRICE |
| commercial | `backend/app/commercial/domain/report_permissions.py` | LABELS? ALL? SALES |
| foundation | `backend/app/foundation/domain/audit_labels.py` | ACTIONS? ENTITIES |
| foundation | `backend/app/foundation/domain/delegations.py` | DELEGABLE |
| foundation | `backend/app/foundation/domain/enums.py` | OrganizationStatus: 'provisioning', 'active', 'suspended', 'inactive', 'archived'? UserStatus: 'active', 'inactive', 'locked' |
| foundation | `backend/app/foundation/domain/log_words.py` | ENTITIES? VERBS? FIELDS? VALUES? LISTS? EXACT |
| foundation | `backend/app/foundation/domain/permission_catalog.py` | MODULE_NAMES? RESOURCE_NAMES? ACTION_NAMES? FOUNDATION_PERMISSIONS? SCOPABLE_OWNER_FIELDS? COMMERCIAL_PERMISSIONS? WORKFORCE_PERMISSIONS? ALL_PERMISSION_CODES? PERMISSIONS_BY_MODULE |
| foundation | `backend/app/foundation/domain/permission_labels.py` | LABELS |
| foundation | `backend/app/foundation/domain/system_roles.py` | _MD_DEFINE? _MD_LISTS? _NCR_ACTION_OWNER? _OPERATIONAL? _OPERATIONAL_READS? _BUSINESS_READS? _SALES_REP? _PRODUCTION_SUPERVISOR? _QUALITY_INSPECTOR? _FACTORY_MANAGER? SYSTEM_ROLES? RETIRED_SYSTEM_ROLES? SYSTEM_ROLE_SCOPE_OVERRIDES |
| foundation | `backend/app/foundation/domain/user_lifecycle.py` | USER_VALID_TRANSITIONS |
| masterdata | `backend/app/masterdata/domain/geography.py` | ARAB_COUNTRIES? COUNTRIES? CITIES |
| masterdata | `backend/app/masterdata/domain/lists.py` | LISTS? TEXT_LISTS? PROTECTED? PARENT? STANDARD |
| masterdata | `backend/app/masterdata/domain/permissions.py` | RESOURCES? ALL? READ? PRODUCT_ACTIONS? LABELS |
| masterdata | `backend/app/masterdata/domain/rules.py` | KEY? KINDS? PROPERTY_KINDS? CURRENCIES? DEFAULT_VAT_RATE |
| notifications | `backend/app/notifications/domain/permissions.py` | RESOURCES? ALL? LABELS |
| notifications | `backend/app/notifications/domain/rules.py` | AUDIENCES? FILTERS |
| platform | `backend/app/platform/domain/enums.py` | PlatformAccountStatus: 'active', 'inactive'? PlatformAccountRole: 'root', 'admin' |
| platform | `backend/app/platform/domain/permissions.py` | PlatformPermission: 'platform:organizations:read', 'platform:organizations:create', 'platform:organizations:update', 'platform:organizations:suspend', 'platform:organizations:activate', 'platform:administrators:read', 'platform:administrators:create', 'platform:administrators:update', 'platform:administrators:deactivate', 'platform:settings:read', 'platform:settings:manage', 'platform:system_health:read', 'platform:audit:read', 'platform:audit:export', 'platform:security_log:read', 'platform:activity_log:read'? PLATFORM_ROLE_PERMISSIONS |
| platform | `backend/app/platform/domain/policies.py` | VALID_TRANSITIONS |
| procurement | `backend/app/procurement/domain/permissions.py` | RESOURCES? ALL? SETTINGS_UPDATE? READ? SUPPLIER_ACTIONS? RECEIPT_ACTIONS? PO_ACTIONS? LABELS |
| procurement | `backend/app/procurement/domain/purchase_orders.py` | STATUSES? RECEIVABLE? FINAL? CURRENCIES? INCOTERMS? PAYMENT_TERMS |
| procurement | `backend/app/procurement/domain/rules.py` | SUPPLIER_STATUSES? SUPPLIER_CATEGORIES? MATERIAL_CATEGORIES? RECEIPT_STATUSES? ZERO? SEVERITY_POINTS? GRADES |
| production | `backend/app/production/domain/arrangement.py` | SORT_KEYS |
| production | `backend/app/production/domain/downtime_rules.py` | PLANNED? LINKABLE_ORDER? CLOCK_SKEW |
| production | `backend/app/production/domain/enums.py` | ProductionRunStatus: 'planned', 'in_progress', 'paused', 'completed', 'cancelled'? ShiftRosterStatus: 'active', 'closed'? ProductionDemandStatus: 'draft', 'ready_for_planning', 'partially_planned', 'planned', 'cancelled'? ProductionAllocationStatus: 'active', 'released'? ProductionDemandPriority: 'low', 'normal', 'high', 'urgent'? WorkCenterType: 'extrusion', 'rewinding', 'packing', 'quality_station', 'generic'? WorkCenterStatus: 'active', 'inactive', 'under_maintenance'? ShiftType: 'morning', 'evening', 'night', 'custom'? ShiftDefinitionStatus: 'active', 'inactive'? ProductionOrderStatus: 'draft', 'released', 'in_progress', 'on_hold', 'completed', 'closed', 'cancelled'? OrderTransitionTrigger: 'manual', 'activity', 'schedule'? ProductionOrderPriority: 'high', 'urgent', 'normal', 'low'? ResultDisposition: 'customer_good', 'stock_good', 'sample', 'scrap', 'rework'? ResultEntryType: 'original', 'correction'? DowntimeCategory: 'planned_maintenance', 'break_meeting', 'no_orders', 'changeover_setup', 'breakdown', 'material_shortage', 'waiting_labor', 'quality_issue', 'utilities', 'other'? DowntimeStatus: 'open', 'closed'? WasteCategory: 'startup_setup', 'changeover', 'process', 'material_defect', 'machine_fault', 'handling_damage', 'contamination', 'other' |
| production | `backend/app/production/domain/order_lifecycle.py` | TERMINAL? NOT_STARTED? OPEN? ALLOCATION_LOCKED |
| production | `backend/app/production/domain/permissions.py` | RESOURCES? ALL? ORDER_TRANSITIONS? RUN_TRANSITIONS? RESULT_ACTIONS? DOWNTIME_ACTIONS? WASTE_ACTIONS? REPORTS? LABELS |
| production | `backend/app/production/domain/result_rules.py` | ZERO? AVAILABLE? FIXED_LOSS |
| production | `backend/app/production/domain/waste_rules.py` | WRITABLE |
| quality | `backend/app/quality/domain/certificates.py` | STATUSES? CERTIFIABLE_RESULTS |
| quality | `backend/app/quality/domain/enums.py` | QualityCheckType: 'in_process_inspection', 'finished_product_inspection', 'sample_inspection', 'reinspection', 'issue_triggered', 'incoming_inspection', 'general'? QualityCheckStatus: 'open', 'under_inspection', 'closed', 'cancelled'? QualityCheckResult: 'accepted', 'rejected', 'conditional_accept', 'needs_reinspection'? DefectCategory: 'dimension', 'thickness', 'surface', 'color', 'strength', 'winding', 'weight', 'packaging', 'labeling', 'finish', 'other'? DefectSeverity: 'minor', 'major', 'critical'? RejectionReason: 'failed_quality_check', 'critical_defect', 'out_of_spec', 'dimension_failure', 'surface_failure', 'packaging_failure', 'labeling_issue', 'other'? Disposition: 'hold', 'scrap', 'rework', 'return_to_process', 'use_as_is'? DispositionStatus: 'pending', 'decided', 'executed'? NCRSourceType: 'internal_production', 'incoming_material', 'supplier', 'warehouse', 'customer_return', 'other'? NCRReportType: 'material_non_conformance', 'product_non_conformance', 'process_non_conformance', 'packaging_non_conformance', 'documentation_non_conformance', 'other' |
| quality | `backend/app/quality/domain/incoming_rules.py` | PARTS |
| quality | `backend/app/quality/domain/ncr.py` | STATUSES? FINAL? SEVERITIES? ROOT_CAUSE_CATEGORIES? ROOT_CAUSE_METHODS? DISPOSITIONS? ACTION_KINDS? ACTION_STATUSES? SUPPLIER_ACTIONS? CLAIM_STATUSES? COSTS? ZERO? RECURRENCE_KEYS |
| quality | `backend/app/quality/domain/permissions.py` | RESOURCES? ALL? SETTINGS_UPDATE? CHECK_ACTIONS? REJECTION_ACTIONS? NCR_ACTIONS? LABELS |
| quality | `backend/app/quality/domain/report_permissions.py` | LABELS? ALL |
| quality | `backend/app/quality/domain/return_rules.py` | PARTS? DISPOSITION_OF? REJECTION_REASON |
| quality | `backend/app/quality/domain/rules.py` | ZERO? ACTIVE? FINAL? ORDER_STATUSES? SEVERITY_RANK |
| quality | `backend/app/quality/domain/specifications.py` | KINDS? TARGET_SOURCES? STANDARD_PARAMETERS? DECIMAL_SEPARATORS |
| shipping | `backend/app/shipping/domain/permissions.py` | RESOURCES? ALL? SETTINGS_UPDATE? SHIPMENT_ACTIONS? RETURN_ACTIONS? LABELS |
| shipping | `backend/app/shipping/domain/returns.py` | KINDS? STATUSES? OPEN? VOID? DEFAULT_TOLERANCE_PCT? ZERO? DELIVERY_REASONS? CUSTOMER_REASONS? REASONS? QUALITY_REASONS |
| shipping | `backend/app/shipping/domain/rules.py` | STATUSES? FINAL? RECEIVED? METHODS? ZERO |
| workforce | `backend/app/workforce/domain/enums.py` | WorkforceMemberStatus: 'active', 'inactive', 'suspended', 'terminated'? EmploymentType: 'employee', 'contractor', 'temporary'? WorkerType: 'driver', 'factory_manager', 'production_manager', 'supervisor', 'operator', 'technician', 'maintenance_technician', 'helper', 'quality_inspector', 'warehouse_staff', 'logistics_coordinator', 'sales_manager', 'sales_rep', 'procurement_officer', 'hr_officer', 'accountant', 'safety_officer', 'admin_support' |

## القيم المستخرجة وفحص التغطية

تربط `shared/i18n/domain-fields.json` التعريفات بقواميسها فقط، ولا تكرر القيم. يستخرج الاختبار القيم من enum وثوابت domain في كل تشغيل؛ إضافة نوع أو قيمة بلا ترجمة مقابلة تفشل CI. أسماء الصلاحيات وأوصافها في المصدر المشترك، ويحتفظ الخادم بعقد السجل القديم عبر قارئ، دون نسخة نصية ثانية في `permission_labels.py`.

اللوحات لا تحتاج جدول labels عامًا: يربط `dashboard-enums.ts` نوع كل توزيع بقاموسه. `machine_fault` قيمة قديمة موجودة في بيانات التوقفات ولها تسمية خاصة بالتوقف، دون تغيير قيم الكود أو قاعدة البيانات. أسماء مراكز العمل المدخلة بلغة واحدة تظل كما هي.

| المصدر | القيم | قاموس الترجمة |
|---|---|---|
| `commercial.CATEGORIES` | `commercial`, `delivery`, `other`, `packaging`, `quality`, `quantity`, `service` | `commercial.ComplaintsCategories` |
| `commercial.CommercialOrderStatus` | `cancelled`, `confirmed`, `converted_to_production`, `draft` | `commercial.commercialOrderStatus` |
| `commercial.CustomerStatus` | `active`, `archived`, `blacklisted`, `inactive`, `on_hold` | `commercial.customerStatus` |
| `commercial.FollowUpPriority` | `high`, `low`, `medium`, `urgent` | `commercial.customerPriorityLevel` |
| `commercial.FollowUpStatus` | `cancelled`, `completed`, `in_progress`, `pending` | `commercial.followUpStatus` |
| `commercial.InteractionType` | `call`, `email`, `meeting`, `visit`, `whatsapp` | `commercial.interactionInteractionType` |
| `commercial.PriorityLevel` | `high`, `low`, `medium` | `commercial.ComplaintsPriorities` |
| `commercial.QuoteStatus` | `accepted`, `draft`, `expired`, `issued`, `rejected` | `commercial.quoteStatus` |
| `commercial.RelationshipStage` | `active_customer`, `contacted`, `lead`, `negotiating`, `prospect`, `qualified`, `repeat_customer`, `strategic_customer`, `trial_customer` | `commercial.customerRelationshipStage` |
| `commercial.STATUSES` | `cancelled`, `closed`, `new`, `pending_closure`, `processing` | `commercial.ComplaintsStatuses` |
| `commercial.SampleDecision` | `accepted`, `pending`, `rejected` | `commercial.sampleDecision` |
| `commercial.SampleEvaluationNextAction` | `close_request`, `further_review`, `proceed_to_quote`, `revise_sample` | `commercial.sampleEvaluationNextAction` |
| `commercial.SampleEvaluationResultStatus` | `accepted`, `needs_modification`, `rejected` | `commercial.sampleEvaluationResultStatus` |
| `commercial.SampleStatus` | `cancelled`, `delivered`, `evaluated`, `in_preparation`, `requested` | `commercial.sampleStatus` |
| `foundation.AccessScope` | `organization`, `own`, `team` | `foundation.accessScope` |
| `foundation.OrganizationStatus` | `active`, `archived`, `inactive`, `provisioning`, `suspended` | `foundation.OrganizationStatus` |
| `foundation.UserStatus` | `active`, `inactive`, `locked` | `foundation.userStatus` |
| `masterdata.KINDS` | `finished`, `material` | `masterdata.Kinds` |
| `masterdata.PROPERTY_KINDS` | `choice`, `number`, `text` | `masterdata.PROPERTY_KINDS` |
| `notifications.CATEGORIES` | `access`, `announcement`, `delegation`, `security`, `work` | `notifications.Categories` |
| `notifications.SEVERITIES` | `important`, `info`, `urgent` | `notifications.severity` |
| `platform.PlatformAccountRole` | `admin`, `root` | `platform.PlatformAccountRole` |
| `platform.PlatformAccountStatus` | `active`, `inactive` | `platform.AdministratorsStatuses` |
| `procurement.MATERIAL_CATEGORIES` | `accessory`, `additive`, `carton`, `core`, `film`, `masterbatch`, `other`, `resin` | `procurement.materialCategory` |
| `procurement.RECEIPT_STATUSES` | `cancelled`, `draft`, `received` | `procurement.receiptStatus` |
| `procurement.STATUSES` | `approved`, `cancelled`, `closed`, `draft`, `partially_received`, `received`, `sent` | `procurement.orderStatus` |
| `procurement.SUPPLIER_CATEGORIES` | `consumables`, `other`, `packaging`, `raw_material`, `services` | `procurement.supplierCategory` |
| `procurement.SUPPLIER_STATUSES` | `approved`, `blocked`, `conditional`, `pending` | `procurement.supplierStatus` |
| `production.DowntimeCategory` | `break_meeting`, `breakdown`, `changeover_setup`, `material_shortage`, `no_orders`, `other`, `planned_maintenance`, `quality_issue`, `utilities`, `waiting_labor` | `production.downtimeEventCategory` |
| `production.DowntimeStatus` | `closed`, `open` | `production.downtimeEventStatus` |
| `production.OrderTransitionTrigger` | `activity`, `manual`, `schedule` | `production.OrderTransitionTrigger` |
| `production.ProductionAllocationStatus` | `active`, `released` | `production.AllocationStatuses` |
| `production.ProductionDemandPriority` | `high`, `low`, `normal`, `urgent` | `production.productionOrderPriority` |
| `production.ProductionDemandStatus` | `cancelled`, `draft`, `partially_planned`, `planned`, `ready_for_planning` | `production.DemandsStatuses` |
| `production.ProductionOrderPriority` | `high`, `low`, `normal`, `urgent` | `production.productionOrderPriority` |
| `production.ProductionOrderStatus` | `cancelled`, `closed`, `completed`, `draft`, `in_progress`, `on_hold`, `released` | `production.productionOrderStatus` |
| `production.ProductionRunStatus` | `cancelled`, `completed`, `in_progress`, `paused`, `planned` | `production.ExecutionStatus` |
| `production.ResultDisposition` | `customer_good`, `rework`, `sample`, `scrap`, `stock_good` | `production.ResultsDispositions` |
| `production.ResultEntryType` | `correction`, `original` | `production.ResultsEntryTypes` |
| `production.ShiftDefinitionStatus` | `active`, `inactive` | `production.shiftDefinitionStatus` |
| `production.ShiftRosterStatus` | `active`, `closed` | `production.ExecutionStatus` |
| `production.ShiftType` | `custom`, `evening`, `morning`, `night` | `production.shiftDefinitionShiftType` |
| `production.WasteCategory` | `changeover`, `contamination`, `handling_damage`, `machine_fault`, `material_defect`, `other`, `process`, `startup_setup` | `production.wasteRecordWasteCategory` |
| `production.WorkCenterStatus` | `active`, `inactive`, `under_maintenance` | `production.workCenterStatus` |
| `production.WorkCenterType` | `extrusion`, `generic`, `packing`, `quality_station`, `rewinding` | `production.workCenterCenterType` |
| `quality.ACTION_KINDS` | `correction`, `corrective`, `preventive` | `quality.ACTION_KINDS` |
| `quality.ACTION_STATUSES` | `cancelled`, `done`, `open` | `quality.ActionStatuses` |
| `quality.CERTIFIABLE_RESULTS` | `accepted`, `conditional_accept` | `quality.qualityCheckResult` |
| `quality.CLAIM_STATUSES` | `accepted`, `claimed`, `none`, `recovered`, `rejected` | `quality.CLAIM_STATUSES` |
| `quality.DISPOSITIONS` | `hold`, `regrade`, `return_to_process`, `return_to_supplier`, `rework`, `scrap`, `sort`, `use_as_is` | `quality.DISPOSITIONS` |
| `quality.DefectCategory` | `color`, `dimension`, `finish`, `labeling`, `other`, `packaging`, `strength`, `surface`, `thickness`, `weight`, `winding` | `quality.qualityDefectDefectCategory` |
| `quality.DefectSeverity` | `critical`, `major`, `minor` | `quality.qualityDefectSeverity` |
| `quality.Disposition` | `hold`, `return_to_process`, `rework`, `scrap`, `use_as_is` | `quality.qualityRejectionDisposition` |
| `quality.DispositionStatus` | `decided`, `executed`, `pending` | `quality.qualityRejectionDispositionStatus` |
| `quality.KINDS` | `attribute`, `numeric` | `quality.ParametersKinds` |
| `quality.NCRReportType` | `documentation_non_conformance`, `material_non_conformance`, `other`, `packaging_non_conformance`, `process_non_conformance`, `product_non_conformance` | `quality.ncrReportReportType` |
| `quality.NCRSourceType` | `customer_return`, `incoming_material`, `internal_production`, `other`, `supplier`, `warehouse` | `quality.ncrReportSourceType` |
| `quality.ORDER_STATUSES` | `completed`, `in_progress`, `on_hold` | `quality.ORDER_STATUSES` |
| `quality.QualityCheckResult` | `accepted`, `conditional_accept`, `needs_reinspection`, `rejected` | `quality.qualityCheckResult` |
| `quality.QualityCheckStatus` | `cancelled`, `closed`, `open`, `under_inspection` | `quality.qualityCheckStatus` |
| `quality.QualityCheckType` | `finished_product_inspection`, `general`, `in_process_inspection`, `incoming_inspection`, `issue_triggered`, `reinspection`, `sample_inspection` | `quality.qualityCheckCheckType` |
| `quality.REINSPECTION_ORDER_STATUSES` | `closed`, `completed`, `in_progress`, `on_hold` | `quality.REINSPECTION_ORDER_STATUSES` |
| `quality.ROOT_CAUSE_CATEGORIES` | `environment`, `machine`, `man`, `material`, `measurement`, `method` | `quality.ROOT_CAUSE_CATEGORIES` |
| `quality.ROOT_CAUSE_METHODS` | `fishbone`, `five_whys`, `other` | `quality.ROOT_CAUSE_METHODS` |
| `quality.RejectionReason` | `critical_defect`, `dimension_failure`, `failed_quality_check`, `labeling_issue`, `other`, `out_of_spec`, `packaging_failure`, `surface_failure` | `quality.qualityRejectionRejectionReason` |
| `quality.SEVERITIES` | `critical`, `major`, `minor` | `quality.qualityDefectSeverity` |
| `quality.STATUSES` | `action`, `cancelled`, `closed`, `draft`, `investigation`, `issued`, `open`, `revoked`, `verification` | `quality.STATUSES` |
| `shipping.CUSTOMER_REASONS` | `customer_cancelled`, `excess_quantity`, `other`, `quality_defect`, `spec_mismatch`, `transit_damage`, `wrong_item` | `shipping.returnReason` |
| `shipping.DELIVERY_REASONS` | `customer_refused`, `no_receiver`, `other`, `quality_issue`, `site_closed`, `transit_damage`, `wrong_address` | `shipping.returnReason` |
| `shipping.KINDS` | `customer`, `delivery` | `shipping.returnKind` |
| `shipping.METHODS` | `carrier`, `factory_delivery`, `pickup` | `shipping.deliveryMethod` |
| `shipping.QUALITY_REASONS` | `other`, `quality_defect`, `quality_issue`, `spec_mismatch`, `transit_damage` | `shipping.returnReason` |
| `shipping.REASONS` | `customer`, `delivery` | `shipping.returnKind` |
| `shipping.STATUSES` | `approved`, `cancelled`, `delivered`, `dispatched`, `draft`, `not_delivered`, `partially_delivered`, `ready`, `received`, `rejected`, `requested`, `returned` | `shipping.STATUSES` |
| `workforce.EmploymentType` | `contractor`, `employee`, `temporary` | `workforce.workforceMemberEmploymentType` |
| `workforce.WorkerType` | `accountant`, `admin_support`, `driver`, `factory_manager`, `helper`, `hr_officer`, `logistics_coordinator`, `maintenance_technician`, `operator`, `procurement_officer`, `production_manager`, `quality_inspector`, `safety_officer`, `sales_manager`, `sales_rep`, `supervisor`, `technician`, `warehouse_staff` | `workforce.workforceMemberWorkerType` |
| `workforce.WorkforceMemberStatus` | `active`, `inactive`, `suspended`, `terminated` | `workforce.workforceMemberStatus` |
