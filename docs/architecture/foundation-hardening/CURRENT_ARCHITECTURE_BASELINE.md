# خط الأساس الحالي للمعمارية — IORP

**التاريخ:** 2026-10-14 · **الفرع:** `fix/production-readiness-20261008` · **الطريقة:** فحص فعلي للمستودع (كود، نماذج، مسارات، اختبارات) + تشغيل أدوات قراءة فقط. لم يُعدَّل أي كود أو بيانات.

> التصنيف المستخدم:
> ✅ **منفّذ ومُتحقَّق** (كود + اختبارات آلية تمر) · 🟨 **منفّذ لكن اختباره غير كافٍ** · 🟥 **منفّذ بعيب مؤكَّد** · ⛔ **غير منفّذ ومطلوب الآن** · 🔮 **متطلب مستقبلي، غير لازم الآن**

## 1. الصورة العامة

| البند | القيمة المقيسة |
|---|---|
| النمط المعماري | Modular Monolith (FastAPI + SQLAlchemy + Alembic + PostgreSQL 16؛ واجهة Next.js 15.5) |
| الوحدات | foundation, platform, commercial, production, quality, procurement, shipping, masterdata, workforce, notifications, dashboard, ai, core |
| مسارات الـAPI | **489** مسارًا (production 93، commercial 86، quality 78، admin 43، shipping 38، platform 33، procurement 33، …) |
| الجداول | 100 جدول محمَّل في الـmetadata؛ **78** تحمل `organization_id`؛ 22 بدونه (منها جداول فرعية تتبع أبًا مملوكًا للمنظمة، وجداول المنصة) |
| الترحيلات | 130 ملف Alembic |
| الاختبارات | خلفية: 2288 اختبارًا ناجحًا في آخر تشغيل كامل (37 دقيقة)؛ واجهة: 262 vitest + 87 node test |
| CI/CD | ⛔ لا يوجد أي خط CI في المستودع (`.github` غير موجود) |

## 2. جرد القدرات

### 2.1 الحدود المعمارية
| القدرة | الحالة | الدليل |
|---|---|---|
| منع استيراد نماذج وحدة من وحدة أخرى | ✅ | `tests/test_module_boundaries.py`؛ الوصول عبر `app/core/interfaces/*` (22 واجهة) |
| كل وحدة الكاتب الوحيد لجداولها، بادئة جداول لكل وحدة | ✅ | أسماء الجداول (`commercial_*`, `production_*` …) + اختبار الحدود |

### 2.2 سياق المستأجر (Tenant Context)
| القدرة | الحالة | الدليل |
|---|---|---|
| استخراج المنظمة من الخادم لا من العميل | ✅ | `app/dependencies.py` `get_current_user`: المستخدم يُقرأ من القاعدة، ويُرفض التوكن إن لم يطابق `organization_id` فيه منظمة المستخدم (السطر ~240)، ثم حالة المستخدم و`token_version` والجلسة الحية `sid` |
| عدم قبول `organization_id` من رأس/استعلام/جسم الطلب | ✅ | بحث: لا يوجد `Header(...organization)` ولا `Query` لمعرّف المنظمة في مسارات المستأجر؛ اختبارات `test_t56_t61_query_org_override…` و`test_t65_body_org_override…` |
| استعلامات مقيَّدة بالمنظمة في طبقة الخدمات | ✅ (فحص ساكن) | فحص آلي لكل `db.get(Model, id)` و`select(...).where(Model.id == …)` في `app/` (عدا platform): 17 حالة مرشحة، **لا ثغرة حقيقية** — كلها إعادة تحميل لسجل سبق التحقق منه، أو جداول إعدادات مفتاحها معرّف المنظمة، أو مهمة خلفية تعمل لكل المنظمات عمدًا |
| التحقق من مراجع الكيانات (FK من الجسم) | ✅ في المواضع المفحوصة | مثال: `procurement/application/purchase_order_service.py:109-150` (`_supplier`، المواد بـ `Material.organization_id == self.org`)؛ `core/tenancy.py validate_same_organization` تعيد 404 مطابقة لغير الموجود |
| اختبارات عزل آلية بين منظمتين | 🟨 | `tests/test_tenant_isolation.py` (65 حالة: المستخدمون، الأدوار، العملاء، المتابعات، القوى العاملة، الإنتاج، الجودة، تعداد UUID، تجاوز المنظمة في الجسم/الاستعلام) + 14 ملف commercial و13 production و4 quality. **لكن:** procurement (33 مسارًا) **0** اختبار عزل، shipping 1، masterdata 1، notifications/announcements 0، delegations 1، التقارير/التصدير جزئي |

### 2.3 قاعدة البيانات
| القدرة | الحالة | الدليل |
|---|---|---|
| ملكية المنظمة صريحة في الجداول الجذرية | ✅ | 78 جدولًا بـ`organization_id` |
| جداول فرعية بلا `organization_id` (تعتمد الربط بالأب) | 🟨 | `commercial_samples`, `commercial_follow_ups`, `commercial_customer_interactions`, أسطر العروض/الطلبات/الشراء/الاستلام/الشحن/المرتجعات/الطلب الإنتاجي — آمنة طالما كل استعلام يمر بالأب؛ تحتاج اختبارات عزل تغطيها |
| مفاتيح أجنبية مركّبة تمنع الإشارة عبر المنظمات على مستوى القاعدة | 🟨 قرار تصميمي | **126** مفتاحًا أجنبيًا بين جداول المستأجرين كلها بسيطة (`id` فقط)؛ السلامة مضمونة في طبقة التطبيق فقط |
| قيود التفرّد ضمن المنظمة | ✅ | كل قيود التفرّد في جداول المستأجرين تتضمن المنظمة أو أبًا مملوكًا، عدا `foundation_users.email` (عالمي عمدًا لأن الدخول بالبريد) |
| Row-Level Security | 🔮 | غير موجود؛ التقييم في تقرير الأمان |

### 2.4 الهوية والجلسات
| القدرة | الحالة | الدليل |
|---|---|---|
| فصل هوية المنصة عن هوية المستأجر | ✅ | جداول `system_platform_accounts` منفصلة؛ `account_type` إلزامي في التوكن ويُفحص؛ `tests/test_platform_isolation.py`, `test_jwt_token_architecture.py` |
| تحقق التوكن (iss, aud, type, jti, exp, nbf) | ✅ | `core/security.py decode_token` (السطر 127-145) |
| تدوير refresh + كشف إعادة الاستخدام + كوكي HttpOnly بمسار محدد | ✅ | `core/security.py rotate_refresh_token`؛ `core/auth_cookies.py` |
| جلسات المستأجر: إبطال فوري، خمول 15 د، حد أقصى 12 س، حد عدد الأجهزة، جلساتي، تنبيه جهاز جديد | ✅ | SEC-001 (`tests/foundation/test_session_security.py`) |
| جلسات المنصة بنفس المستوى | 🟥 | `dependencies.py:137-165` لا يفحص `sid`؛ لا حد أقصى مطلق (`security.py:234` يطبّقه على `tenant` فقط)؛ لا مراقب خمول في واجهة المنصة؛ لا «جلساتي» |
| قفل الحساب + تحديد المعدل | ✅ (نسخة واحدة) | `core/login_protection.py`؛ `core/rate_limit.py` في ذاكرة العملية |
| إعادة تعيين/تفعيل كلمة المرور بالرابط فقط | ✅ | SEC-002/003 (`tests/foundation/test_account_activation.py`) |
| MFA لحسابات المنصة | ⛔ | لا حقول ولا مسار في `platform/infrastructure/models.py` ولا `PlatformAuthService.login` |
| إعادة المصادقة للعمليات الحساسة | ⛔ | لا آلية step-up |

### 2.5 الصلاحيات
| القدرة | الحالة | الدليل |
|---|---|---|
| صلاحيات المستأجر لكل مسار + اختبار 403 حقيقي | ✅ | `tests/test_all_route_authorization.py`؛ مراجعة `docs/security/authorization-audit-2026-10-07.md` |
| صلاحيات المنصة (Root/Admin) | ✅ مع ملاحظات | `platform/domain/permissions.py`: 16 صلاحية؛ الأرشفة (لا رجعة فيها) تحت `ORGANIZATIONS_SUSPEND` نفسها؛ حصة التخزين وإرسال رابط الجذر تحت `ORGANIZATIONS_UPDATE` المتاحة لدور Admin |
| مسؤول المنصة لا يرى بيانات المستأجر التجارية | ✅ | لا مسار منصة يقرأ جداول الأعمال؛ لا انتحال هوية (impersonation) |

### 2.6 الملفات والتقارير
| القدرة | الحالة | الدليل |
|---|---|---|
| مفاتيح تخزين مقسّمة بالمنظمة | ✅ | `core/files.py:167` `organizations/{org}/{module}/…` |
| تحميل المرفقات بعد تحقق الملكية | ✅ | `commercial/api/routes_complaints.py:113-121` (شرط `organization_id` + صلاحية القراءة على الراوتر)؛ `quality/api/routes_ncr.py:217`؛ `shipping/api/routes_shipments.py` عبر الخدمة |
| حصة تخزين لكل منظمة | ✅ | `core/files.py usage/quota/store` |
| تقارير PDF مع فحص صلاحية التعريف | ✅ | مراجعة 2026-10-07 + `tests/test_reporting_renderer.py`؛ عارض Gotenberg معزول الشبكة (`docker-compose.yml`) |
| شعار المنظمة في مسار المنصة بـ `Cache-Control: public` | 🟥 (منخفض) | `platform/api/routes_platform_admin.py:148` |

### 2.7 المهام الخلفية والذاكرة المؤقتة
| القدرة | الحالة | الدليل |
|---|---|---|
| مهمة البدء التلقائي للطلبات الإنتاجية | ✅ | `production/application/order_status_service.py:186-198` تعالج كل منظمة بتاريخها المحلي وتقفل الصف |
| تنظيف السجلات/الأرشفة | ✅ | `foundation/application/security_log.py purge`، أرشفة سجل النشاط |
| ذاكرة مؤقتة (cache) | لا يوجد غير `lru_cache` للإعدادات | `core/config.py:115` — لا خطر تسرب بين المستأجرين |
| WebSocket/زمن حقيقي | لا يوجد | — |

### 2.8 إدارة المنصة ودورة حياة المنظمة
| القدرة | الحالة | الدليل |
|---|---|---|
| آلة حالات: provisioning→active⇄suspended⇄inactive→archived | ✅ | `platform/domain/policies.py`؛ `tests/test_organization_lifecycle.py` (T01-T38) |
| منع الحذف، سبب إلزامي للأرشفة، حجب الدخول عند الإيقاف | ✅ | `routes_platform_admin.py:238-246`؛ اختبارات login gate |
| حالة `provisioning` مستخدمة فعليًا | 🟨 | المنظمات تُنشأ `ACTIVE` مباشرة (`foundation/infrastructure/organization_queries.py:73`) |
| سجل تدقيق المنصة | 🟥 جزئيًا | يُكتب **بعد** commit العملية في معاملة منفصلة؛ تغيير حصة التخزين **غير مُدقَّق إطلاقًا** (`routes_platform_admin.py:121-133`) |
| إبلاغ مدير المنظمة بإجراءات المنصة على منظمته | ⛔ (P1) | لا يوجد |
| قائمة المنظمات بأداء قابل للتوسع | 🟥 (P1) | N+1: استعلامان لكل منظمة في `_summarize` + اسم المنفّذ لكل منظمة في `_summary_response`؛ بلا صفحات |
| الخطط/الاشتراكات/الوحدات المفعّلة | 🔮 | لا يوجد؛ الموجود: حصة التخزين، `max_sessions_per_user` |

### 2.9 النشر والتشغيل
| القدرة | الحالة | الدليل |
|---|---|---|
| حواجز إعدادات الإنتاج (DEBUG، SECRET_KEY، كوكي Secure، SMTP TLS، روابط HTTPS) | ✅ | `core/config.py` model validator (السطر ~85-105) |
| الأسرار خارج المستودع | ✅ | `.env` في `.gitignore` لكلا المشروعين |
| توثيق الـAPI مكشوف | 🟥 | `/docs`, `/redoc`, `/openapi.json` مفعّلة في كل البيئات (`main.py:212` بلا `docs_url=None`) |
| ترويسات أمان (HSTS, CSP, X-Frame-Options, nosniff) | ⛔ | الخلفية بلا أي ترويسة؛ `frontend/next.config.mjs` يضيف ترويسات لصفحات إعادة التعيين فقط |
| CORS | ✅ مع ملاحظة | أصول محددة؛ `allow_headers=["*"]` (`core/middleware.py:27-33`) |
| معرّف الطلب للتتبع | ✅ | `RequestIdMiddleware` (`X-Request-ID`) |
| فحص الاعتماديات | 🟥 | `npm audit --omit=dev`: 3 high + 1 moderate (postcss, sharp, source-map-js عبر next 15.5.27)؛ `pip-audit` غير مثبت → غير متحقق |
| النسخ الاحتياطي والاستعادة | ⛔ | لا سكربت ولا توثيق؛ `docker-compose.yml` volume فقط؛ الملفات على قرص محلي؛ RPO/RTO غير معرّفين (يؤكده `docs/audits/2026-10-08/ASSESSMENT.md:113`) |
| تحديد المعدل لعدة نسخ من الخادم | 🔮 | في ذاكرة العملية — صحيح لنسخة واحدة |

## 3. ما يجب ألا يتغير
- نموذج «قاعدة بيانات واحدة مشتركة + `organization_id`» ونمط الوحدات والواجهات الحالية.
- آلية استخراج المنظمة من المستخدم في الخادم، و404 المطابقة لغير الموجود.
- آلة حالات المنظمة ومنع الحذف.
- فصل هوية المنصة عن المستأجر وعدم وجود انتحال هوية.
