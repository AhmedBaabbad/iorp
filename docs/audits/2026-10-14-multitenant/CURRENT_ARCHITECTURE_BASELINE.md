# خط أساس المعمارية الحالية

تاريخ الفحص: 2026-10-14. نطاق هذه الجولة: الخطوات A–C قبل بوابة الموافقة D. لم نعدّل كود التطبيق أو الترحيلات أو بيانات الشركات. المستودع يتضمن تعديلات سابقة؛ التقييم يصف نسخة العمل الحالية ولا ينسب تغييرات سابقة لهذه المهمة.

## الحكم التنفيذي

يوجد تطبيق متعدد المنظمات بالفعل؛ لا حاجة لإعادة بنائه. توجد اختبارات عزل حقيقية، لكن لا توجد أدلة كافية لمنح موافقة إطلاق شامل لشركة مستقلة ثانية. الفصل الوظيفي بالواجهة ليس شهادة عزل. يلزم إغلاق P0 في التقرير المرافق ثم إعادة اختبارات سلبية أوسع على PostgreSQL وبيئة staging.

## الجرد المبني على الكود

المسارات التالية نسبية إلى جذر المستودع. «متحقق» يعني تحققًا في النطاق المذكور فقط.

| القدرة | الحالة | الدليل وحدود التحقق |
|---|---|---|
| Modular Monolith | منفذ؛ فحص بنيوي | backend/app يحوي foundation, platform, commercial, production, quality, shipping, procurement, workforce, dashboard, notifications وcore. توجد طبقات api/application/domain/infrastructure وواجهات core/interfaces. لم ننفذ تحليل اعتماد كامل لكل import. |
| الفصل بين Platform وTenant | منفذ ومختبر جزئيًا | dependencies.py وplatform/api/routes_platform_auth.py؛ رفض account_type غير المناسب. اختبارات test_platform_isolation.py. |
| سياق المنظمة | منفذ ومختبر جزئيًا | dependencies.py:get_current_user يربط الهوية بالمنظمة؛ core/tenancy.py يحتوي TenantContext وفحص تطابق المنظمة. لا تكفي هذه المركزية وحدها لإثبات سلامة كل repository. |
| JWT وRefresh | منفذ مع عيب مؤكد في مسار Platform | core/security.py يتحقق issuer/audience/type وينفذ تدوير refresh؛ dependencies.py لا يفحص session_active لمنصة الإدارة كما يفعل للمستأجر. |
| MFA للمنصة | غير منفذ ومطلوب الآن | مسار login ينشئ الجلسة بعد كلمة المرور؛ لم نجد enrollment/challenge/recovery خاصًا بعامل ثانٍ في Platform/Core المفحوصين. |
| RBAC المنصة | منفذ واختباره غير شامل | platform/domain/permissions.py وصلاحيات endpoints؛ دوران Root/Admin. استعادة جذر المنظمة مشتركة مع organizations:update. |
| الواجهة | منفذة واختبارها غير شامل | frontend/src/features/platform وapp/platform؛ صفحة تفاصيل المنظمة تعرض الجذر والأدوار والحالة والحصة. بعض قرارات العرض تعتمد isRoot؛ يجب توحيدها مع permissions دون جعل الواجهة حارس الأمان. |
| دورة حياة المنظمة | منفذة مع عيب معاملاتي | platform/domain/policies.py؛ active/suspended/inactive/archived/provisioning. إلغاء جلسات المنظمة موجود. الحفظ يسبق تسجيل تدقيق الانتقال. |
| سجلات التدقيق | منفذة مع فجوات | core/audit.py وplatform/api/routes_platform_audit.py؛ middleware يولد request_id. تحديث حصة التخزين لا يكتب سجلًا صريحًا في المسار المتتبع. |
| قاعدة البيانات | منفذة واختبارها غير شامل | SQLAlchemy/PostgreSQL/Alembic؛ organization_id في الجذور وملكية موروثة في بعض التوابع. مفاتيح أجنبية أحادية للموارد لا تثبت تطابق المنظمة على مستوى قاعدة البيانات. |
| ملفات وحصص | منفذة واختبارها غير شامل | core/files.py: مفاتيح organizations/{id}، تحقق الأنواع والحجم وحصة المنظمة؛ يلزم اختبار تنزيل ومعرف ملف أجنبي لكل وحدة، وليس الاعتماد على شكل المسار. |
| تقارير | منفذة واختبارها غير شامل | core/reporting/routes.py: get_current_user وReportingService(current.tenant)، صلاحية التقرير، private/no-store، CSP للمعاينة. Gotenberg معزول في docker-compose.yml. ملفات اختبارات التقارير موجودة؛ لم تُشغّل كلها في هذه الجولة. |
| Cache | جزئي ومحدود | lru_cache للإعدادات وlookup_cache ضمن ExecutionService؛ لم نجد Redis/business cache عام في البحث. يلزم تتبع عمر service قبل تقرير خطر تسرب cache. |
| مهام خلفية | منفذة جزئيًا | production/application/order_scheduler.py يعمل داخل العملية وينفذ auto_start_due_orders؛ لا دليل على منصة queues موزعة. التعليق بأنه idempotent يحتاج إثبات تزامن PostgreSQL. |
| WebSocket | لم يُعثر على تنفيذ في البحث الحالي | ليس مطلبًا لإضافته الآن. |
| إعدادات الإنتاج | منفذة واختبارها غير شامل | core/config.py يرفض DEBUG ومفتاحًا افتراضيًا وSMTP غير مشفر وcookies غير آمنة في production. لا يعني ذلك أن بيئة النشر الحقيقية تلتزم بها. |
| OpenAPI وHeaders | غير مكتمل بحسب سياق النشر | main.py يستخدم إعداد FastAPI الافتراضي للتوثيق؛ middleware لا يثبت سياسة security headers شاملة. reverse proxy الإنتاجي لم يُتحقق منه. |
| النسخ والاستعادة | غير متحقق ومطلوب قبل الإطلاق | docker-compose volume ليس backup. لا سكربت نسخ/استعادة مثبت في المسارات التي بحثناها؛ وجود خدمة خارج المستودع غير معلوم. RPO/RTO غير مقاسين. |
| CI | غير متحقق ومطلوب | لا مجلد .github في النسخة الحالية ولا pipeline مثبت بالبحث؛ قد توجد CI خارج المستودع. |
| فحص الاعتماديات | غير متحقق حديثًا | توجد نتائج سابقة في docs/verification/production-readiness؛ لم نعد تشغيل تدقيق شبكي حديث ولا نعتبر القديم شهادة خلو من الثغرات. |
| الخطط والفوترة | مستقبل، لا تنفيذ الآن | حصة تخزين قائمة وصلاحيات منظمة؛ لم نجد في النطاق المفحوص نموذج اشتراك تجاري متكامل. لا ننشئ جداول افتراضية. |

## ما يبقى كما هو

المودلات التشغيلية، معرفات المنظمات، بيانات ريحانة والمتحدة، Modular Monolith، الجلسات وRBAC القائمان، آلة الحالات، تقديم استعادة كلمة المرور كرابط، ومنع الحذف الدائم. لا Microservices، ولا قاعدة لكل شركة، ولا RLS تلقائيًا، ولا انتحال عميل.

## حدود التغطية

هذا جرد موجه لعناصر الثقة والتشغيل؛ لم تُفحص كل استعلامات كل ملف، ولم يُنفذ اختبار اختراق خارجي أو تحميل أو استعادة نسخة أو ترحيل في قاعدة العمل. تفاصيل الاختبارات المنفذة في TEST_AND_ACCEPTANCE_MATRIX.md. أي فراغ تغطية يبقى معلنًا، لا يُحوّل إلى «سليم».
