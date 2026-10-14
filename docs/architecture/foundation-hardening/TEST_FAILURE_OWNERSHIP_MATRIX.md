# مصفوفة ملكية الاختبارات الفاشلة — IORP

**التاريخ:** 2026-10-14 · **المراجع:** Claude (مراجع مستقل). كل حكم مبني على تشغيل فعلي وفحص سلوك التطبيق بطلب HTTP حقيقي، لا على قراءة الاختبار وحدها.
**بيئتا التشغيل:**
- **E1** — المفسّر العام (FastAPI 0.115 / Starlette 0.37.2): **2302 ناجح، 24 فاشل** (23 بعد إعادة التشغيل).
- **E2** — بيئة معزولة مطابقة لـ `pyproject.toml` (FastAPI 0.143.1 / Starlette 0.52.1): **1895 ناجح، 43 فاشل، ~390 اختبارًا أقل** (انظر T-ENV).

## أ. عيب سلامة الاختبارات — الأعلى أولوية (T-ENV)

| البند | التفاصيل |
|---|---|
| **الوصف** | في FastAPI 0.143 صار `app.routes` يحوي غلاف `_IncludedRouter` لكل راوتر مضمَّن: **6** مسارات ظاهرة بدل **489**. كل اختبار حماية يمر على `app.routes` يرى قائمة شبه فارغة |
| **الأثر المؤكَّد** | `test_all_route_authorization::test_every_api_route_declares_a_policy…` **ينجح دون فحص شيء** في E2 (بينما يكشف في E1 مسارين غير مسجلين)؛ `test_no_permissions_cannot_access_operational_route` **يُتخطى بالكامل** (`NOTSET`)؛ حارس المسح `test_every_swept_module_identifier_route_is_covered` **ينجح فارغًا**. اختبارات أخرى تفشل بصوت (`assert 0 >= 14`، `no route …`) |
| **التطبيق نفسه** | يعمل: 1895 اختبار HTTP نجح في E2، و`openapi()` يعرض 372 مسارًا |
| **الخاطئ** | **بيئة الاختبار/الاختبارات**: `pyproject.toml` يسمح بـ `fastapi>=0.120,<1.0` دون حد أعلى مختبر، واختبارات الحماية تعتمد على بنية داخلية ولا تتحقق من حد أدنى لعدد المسارات |
| **التصحيح المطلوب** | (1) دالة مساعدة واحدة في `tests/` تجمع المسارات الفعلية (تتعامل مع `_IncludedRouter`) يستخدمها كل اختبار حماية؛ (2) **تأكيد حد أدنى** (`len(routes) >= 450`) في كل اختبار يمر على المسارات حتى لا ينجح فارغًا أبدًا؛ (3) حد أعلى مُختبر لـ FastAPI في `pyproject.toml` حتى تُحدَّث الاختبارات؛ (4) ملف قفل للنسخ |
| **المالك** | Codex (مالك التنفيذ) — بنية الاختبار المشتركة |

## ب. فشل في E1 (والمكرر في E2)

| # | الاختبار | الميزة | المتوقع (في الاختبار) | الفعلي (متحقق بطلب حقيقي) | الخاطئ | التصحيح | المالك |
|---|---|---|---|---|---|---|---|
| 1 | `test_organization_root::t01_root_cannot_be_soft_deleted` | ADR-010 | DELETE بلا جسم → 403 | 422 (السبب إلزامي)؛ **مع سبب → 403 `CANNOT_DEACTIVATE_ORGANIZATION_ROOT`** | الاختبار | إرسال `{"reason": …}` وإبقاء توقع 403 | صاحب ADR-010 |
| 2 | `…::t02_root_cannot_be_hard_deleted` | ADR-010 | `/hard` → 403 | 404 (المسار أُزيل عمدًا؛ الجذر سليم) | الاختبار | توقع 404/405 + التحقق أن الجذر ما زال نشطًا | صاحب ADR-010 |
| 3 | `…::t03_root_name_is_immutable` | ADR-010 | PATCH الاسم → 403 `CANNOT_MODIFY_ROOT_IDENTITY` | 400 «البيانات الشخصية عبر صاحب الحساب فقط» — **ما زال ممنوعًا** | الاختبار | توقع 400 + الرمز الجديد؛ والتحقق أن الاسم لم يتغير | صاحب ADR-010 |
| 4 | `…::t04_root_email_is_immutable` | ADR-010 | 403 | 400 — ممنوع | الاختبار | كما في 3 | صاحب ADR-010 |
| 5 | `…::t06_root_phone_can_change` | ADR-010 | المسؤول يغيّر الهاتف → 200 | 400 — الهاتف صار بيانات شخصية للمالك | الاختبار | توقع الرفض، أو نقله لاختبار الملف الشخصي | صاحب ADR-010 |
| 6 | `…::t09_legacy_hard_route_…` | ADR-010 | `/hard` يعطّل | 404 | الاختبار | حذف الحالة (المسار أُزيل) أو توقع 404 | صاحب ADR-010 |
| 7 | `…::t10_normal_user_can_be_deactivated` | ADR-010 | DELETE بلا جسم → 200 | 422؛ **مع سبب → 200 inactive** | الاختبار | إرسال سبب | صاحب ADR-010 |
| 8 | `…::t15_update_body_cannot_set_root_flag` | ADR-010 | 200 مع تجاهل الحقل | 422 `extra_forbidden` — **أشد أمانًا** | الاختبار | توقع 422 والتحقق أن العلم لم يتغير | صاحب ADR-010 |
| 9–13 | `test_follow_up_deactivation::t01_t05_deactivation_guard_by_status` (×5) | ADR-010 | 200/409 | 422 (السبب مفقود)؛ **مع سبب → 409 `USER_HAS_OPEN_DEPENDENCIES`** عند متابعات مفتوحة | الاختبار | إرسال سبب؛ إبقاء توقعات 200/409 | صاحب ADR-010 |
| 14 | `…::t02_patch_status_change_requires_lifecycle_endpoint` | ADR-010 | 400 | 422 (`status` حقل ممنوع) — ما زال مرفوضًا | الاختبار | قبول 422 | صاحب ADR-010 |
| 15 | `…::t02b_hard_delete_route_is_also_guarded` | ADR-010 | `/hard` → 409 | 404 | الاختبار | المسار أُزيل؛ يبقى حارس DELETE (رقم 9) | صاحب ADR-010 |
| 16 | `…::t22_t24_reassign_then_deactivate_preserves_history` | ADR-010 | 200 | 422 (السبب) | الاختبار | إرسال سبب | صاحب ADR-010 |
| 17 | `test_login_protection::t28_t29_t38_t39_…unlock` | ADR-010 | unlock بلا جسم → 200 | 422 (السبب إلزامي) | الاختبار | إرسال سبب | صاحب ADR-010 |
| 18 | `test_email_identity::t19_t23_…root_immutability` | ADR-010 | 403 | 400 — ممنوع | الاختبار | توقع 400 والتحقق من عدم التغيير | صاحب ADR-010 |
| 19 | `test_rbac_decisions[DELETE …/hard]` | ADR-010 | المسار موجود | أُزيل | الاختبار | حذف الحالة من القائمة | صاحب ADR-010 |
| 20 | `test_all_route_authorization::test_every_api_route_declares_…` (E1 فقط) | ADR-010 | كل مسار له سياسة أو مسجل كذاتي | `/auth/me/email-change` و`/confirm` غير مسجلين | **الاختبار (سجل المسارات)** — المساران ذاتيان فعلًا: `get_current_user` + كلمة المرور الحالية + تحديد معدل (3 و5)، ويعملان على `current.user` فقط | إضافتهما إلى `PUBLIC_OR_SELF` مع تعليق | صاحب ADR-010 |
| 21 | `test_quotation_document::test_arabic_document_content` | الوحدات | النص «رول» | «لفة» — تغيير مقصود في `app/core/units.py` (والواجهة `common.json`) ومتسق مع commit `17d3cd5` | الاختبار | توقع «لفة» | صاحب ميزة الوحدات |
| 22 | `test_shipments::test_delivery_note_document_in_arabic_and_english` | الوحدات | «رول» | «لفة» | الاختبار | كما في 21 | صاحب ميزة الوحدات |
| 23 | `foundation/test_session_security::…email…` (اختباري) | ADR-010 | المسؤول يغيّر البريد | ممنوع (400) | الاختبار | **أُصلح** — يتحقق الآن من المنع (9/9) | Claude ✅ |
| W1 | `frontend shipments.test.tsx` (×2) | الوحدات | خيار «رول» ونص «120 رول» | «لفة» | الاختبار | توقع «لفة» | صاحب ميزة الوحدات |
| W2 | `frontend sample-properties.test.tsx` | الوحدات | «المقاس (mm)» | الوحدة تُترجم الآن (`useUnitLabel`) | الاختبار | توقع الوحدة المترجمة | صاحب ميزة الوحدات |
| — | `test_batch1_isolation::test_foreign_carrier_reference_rejected` | Codex | — | نجح بعد تعديل Codex | — | — | ✅ |
| — | `test_alembic_imports_all_runtime_tables_in_fresh_interpreter` | — | — | نجح في E1 وE2 وفرديًا | — | لا تغيير | ✅ |

## ج. فشل في E2 فقط (سببه T-ENV)
| الاختبار | السبب |
|---|---|
| `test_procurement::test_every_route_declares_a_permission…`، `test_production_rbac` (×2)، `test_quality_inspections::test_every_quality_route…`، `test_shipments::test_every_shipping_route…`، `test_customer_reports::test_customer_shortcut_route…`، `test_rbac_decisions` (14 حالة «no route»)، `test_issuing_a_replacement_certificate_also_needs_revoke`، `test_cross_tenant_sweep::test_every_identifier_route…` | كلها تقرأ `app.routes` فترى 6 مسارات. **ليست عيوبًا في التطبيق.** تُصلح مع T-ENV |

## الحكم
- **لا يوجد اختبار يجب تخفيف توقعه الأمني.** كل فشل ADR-010 سببه تغيّر شكل الطلب (السبب الإلزامي) أو رمز الخطأ، و**الحماية الفعلية متحققة بطلبات حقيقية**: الجذر لا يُعطَّل (403)، `/hard` أُزيل، البيانات الشخصية لا يغيرها المسؤول، المستخدم ذو المتابعات المفتوحة محمي (409)، علم الجذر لا يُضبط (422).
- المساران الجديدان للبريد محميان فعلًا؛ ينقصهما التسجيل في سجل الاختبار فقط.
- **العيب الحقيقي الوحيد عالي الخطورة هو T-ENV**: اختبارات الحماية قد تنجح فارغة تحت النسخ المعلنة.
