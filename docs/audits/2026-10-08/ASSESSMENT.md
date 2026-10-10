# IORP Architecture & SaaS Readiness Assessment

تاريخ التدقيق: **2026-10-08**. النتيجة: **Needs Revision — لا توجد حاليًا أدلة كافية لاعتماد الإنتاج أو جاهزية SaaS**.

هذا تدقيق للشيفرة الحالية والبيئة المحلية، وليس شهادة اختراق أو اعتمادًا لبيئة إنتاج غير متاحة. لم يُعدّل كود الإنتاج أو الاعتماديات أو إعدادات الأعمال أثناء التدقيق. الملفات المضافة أدوات تحقق وتقرير وسجلات أدلة فقط.

## A. Executive Summary

المشروع **Modular Monolith** فعلي: واجهة Next.js/React، وخدمة FastAPI واحدة، وقاعدة SQLAlchemy/PostgreSQL مشتركة. التقسيم حسب القدرات التجارية مناسب لحجمه. توجد قواعد أعمال وحالات انتقال وصلاحيات إجراءات، وفصل هوية المنصة عن هوية المؤسسة. Master Data يملك المنتجات وتعريف خصائصها، وتوجد عقود لتبادل بيانات المبيعات والإنتاج. هذه أسس قابلة للتطوير دون التحول إلى Microservices.

الأدلة الإيجابية: نجح **682 اختبارًا** مختارًا للخلفية يشمل الصلاحيات والعزل والمصادقة وحدود الوحدات؛ ونجح **191 اختبار مكونات واجهة**. نجحت **12 تجربة PostgreSQL** للتزامن وبعض الهجرات، منها منع تجاوز التخصيص وتعارض الإغلاق مع تسجيل النتيجة. نجاحها لا يثبت جميع المسارات أو جاهزية التشغيل.

الموانع الأهم: إصدار Next.js المقفل يقع ضمن تنبيه حرج متعلق بخوادم Windows؛ وبيئة Python المستخدمة تحتوي Starlette وpython-multipart بإصدارات متأثرة بتنبيهات حجب خدمة. Alembic لا يُحمّل جداول Master Data الخمسة في metadata، ما يعرّض توليد الهجرات لمقترحات حذف خاطئة. إعداد production يسمح حاليًا بوضع البريد console الذي يسجّل محتوى رسائل إعادة تعيين كلمة المرور. لا يوجد دليل قابل للتحقق على استعادة نسخة احتياطية أو مسار نشر محكوم آليًا.

ثبت تسرب **عدد** العينات خارج نطاق ملكية المستخدم داخل المؤسسة في `/dashboard/summary`؛ لم يثبت في هذه التجربة تسرب بين مؤسستين. توجد أيضًا فجوات في ذرية سجل التدقيق، وفي اتساق ملفات التخزين مع قاعدة البيانات، واعتماديات عابرة للوحدات رغم نجاح فحص imports الحالي.

لـSaaS: organization موجودة أصلًا، لكن العزل يعتمد على التطبيق، والتخزين محلي، وحدود معدل الطلبات في ذاكرة العملية، ونموذج الهوية يربط المستخدم بمؤسسة واحدة. يلزم قرار تشغيلي واختبارات أوسع، لا إعادة كتابة المشروع. الأداء تحت الحمل، RPO/RTO، الاستعادة، والنشر متعدد النسخ **NOT VERIFIED**.

## نطاق الأدلة وحدودها

- نقطة Git: `905c3a4332fe58645ab7248ac52e5d6761f7fa09`، مع تغييرات كثيرة معدلة وغير متتبعة موجودة مسبقًا؛ التقرير يخص **working tree**، وليس ذلك commit وحده.
- [inventory.json](inventory.json): 407 مسارات API، و92 جدول ORM، و68 جدولًا يحمل `organization_id` مباشرة، و24 جدولًا دون ذلك العمود. بعضها تابع لأب مملوك للمؤسسة، وبعضها للمنصة؛ غياب العمود وحده ليس ثغرة.
- الجرد يحفظ SHA-256 لملفات backend المفحوصة، وسياسات المسارات، والفهارس والمفاتيح والعلاقات ومواقع imports وقراءات metadata.
- فحص التسليم [verification.json](verification.json) أكد ثبات ملفات backend المفهرسة وعددها **363** منذ الجرد، وعدم وجود رابط دليل محلي مكسور في التقرير.
- شمل الجرد جميع ملفات Python في `backend/app`؛ المراجعة اليدوية تعمقت في المسارات الحرجة وأمثلة كل وحدة. لم تُثبت سلامة كل استعلام في جميع التركيبات الممكنة.
- فُحصت ADR-005/006/007/008، ووثائق الحدود والعزل والهوية والتدقيق، ثم قورنت بالتنفيذ. التقارير السابقة ليست دليل نجاح لهذا التدقيق.
- الاختبارات الوظيفية المعتادة تستخدم SQLite؛ تجارب PostgreSQL المعزولة مذكورة منفصلة. لم نغيّر جداول التطبيق أو ننفّذ upgrade/downgrade عليها.
- لم يُنفذ اختبار استغلال RCE أو اختبار ضغط على الخدمة الحية. فحص الأسرار محدود بالتواقيع والملفات المتتبعة الحالية، لا تاريخ Git كاملًا.

## B. Architecture Map

```text
Browser: Next.js App Router / React / next-intl
  → feature API clients / auth state / shared UI
  → /api/v1 + Bearer access token; refresh cookie HttpOnly
FastAPI composition: app/main.py + app/dependencies.py
  → tenant identity: Foundation → TenantContext + permission/scope checks
  → platform identity: Platform → separate account type and permissions
  → Commercial / Production / Quality / Shipping / Procurement / Workforce / Master Data
  → domain rules + application services + own repositories/models
  → one PostgreSQL database / shared SQLAlchemy Base / Alembic
Cross-module contracts: core/interfaces → providers registered at composition root
Actual exceptions: foreign metadata-table reads, foreign model imports, core → foundation/platform
Events: business histories + ShippingEvent persisted with organization; no active broker/consumer found
External systems: SMTP; HTTP → nginx report gateway → isolated Gotenberg/Chromium
Storage: local uploads/organizations/{organization_id}/...
Jobs: optional in-process production auto-start; standalone CAPA reminder CLI
Infrastructure in repository: PostgreSQL + report gateway/renderer compose; no app deployment pipeline
```

### ملكية الوحدات واستقلاليتها

| الوحدة | ملكية البيانات/القدرة | التماسك | استقلال التغيير والعقد والبيانات | إمكانية الفصل لاحقًا |
|---|---|---|---|---|
| Platform | system_*، إدارة المنصة وتهيئة المؤسسات | جيد | هوية منفصلة؛ provisioning عبر protocol؛ FK وبعض core dispatch تربطها بالباقي | ممكن بجهد متوسط؛ لا حاجة الآن |
| Foundation | المؤسسات والمستخدمون والأدوار والصلاحيات والهوية البصرية والسجلات | متوسط؛ خدمات واسعة | عقد هوية موجود، لكن بقية الوحدات تقرأ internals؛ FoundationService كبير | صعب دون فصل العقود والمعاملات أولًا |
| Commercial | العملاء، المتابعات، العينات، العروض، أوامر البيع | جيد ضمن رحلة العميل | عقود Sales Order جيدة؛ اعتماد مباشر على Foundation؛ child rows تعتمد عزل الأب | ممكن بعد ضبط عقود الهوية والقراءة |
| Production | الطلبات، التخصيص، الأوامر، التنفيذ، النتائج، الهدر والتوقف | جيد لكن واسع | عقود Commercial وclose guards؛ معاملات/FK مشتركة وقراءات هوية | تكلفة عالية؛ الحفاظ على monolith أنسب حاليًا |
| Quality | الفحوص، الرفض، NCR/CAPA، المواصفات والشهادات | جيد | reads وlocks على جداول Production/Commercial/Shipping/Procurement | فصل مكلف بسبب الاتساق والمعاملات |
| Shipping | الشحن والتسليم والمرتجعات والمرفقات والأحداث | جيد | يقرأ جداول العملاء والإنتاج والجودة مباشرة؛ يملك أحداثه | متوسط/مرتفع بعد تثبيت العقود |
| Procurement | الموردون والمواد والأوامر والاستلام | جيد | ملكية جداول واضحة؛ قراءات Quality/Foundation مباشرة | متوسط بعد تثبيت عقد الجودة |
| Workforce | أفراد القوى العاملة | جيد | صغير، FK إلى Foundation، عقود query موجودة | أسهل نسبيًا؛ لا مبرر لنشر مستقل |
| Master Data | المنتجات والخصائص والقوائم والإعدادات | جيد | protocol وholders؛ كل وحدة تكتب سجلاتها عند ترحيل القيم؛ transaction مشتركة | جيد داخل monolith؛ الترحيل الجماعي يحتاج إعادة تصميم عند الفصل |
| Dashboard/Reporting | read composition والعرض؛ ليس مالك بيانات الأعمال | متوسط | dashboard العام يقرأ عدة نماذج؛ reporting يقرأ هوية عبر metadata أيضًا | يتطلب عقود قراءة مستقرة |
| Core | أمن وبنية تقنية وعقود وتخزين وتقارير | مختلط | يعتمد أحيانًا على Foundation/Platform؛ بعض protocols تستقبل SQLAlchemy Session | ليس طبقة مستقلة كليًا |

المشروع ليس Distributed Monolith منتشرًا عبر خدمات أعمال متعددة حاليًا؛ الاتصال البعيد الرئيس هو renderer والبريد. مشكلة الترابط تقع داخل monolith. وجود FK عابر للوحدات قد يكون مقبولًا لحفظ سلامة البيانات، لكنه يجب أن يكون قرارًا موثقًا، لا استقلالية مُدّعاة.

### التدفقات وحدود الثقة

1. Master Data → خصائص العينة/بند البيع → أمر بيع مؤكد → طلب إنتاج → تخصيص → تنفيذ → نتيجة أمر → فحوص جودة → شحن/مرتجع. العقود والحالات موجودة؛ ليس كل الربط معزولًا عن الجداول الأجنبية.
2. طلب HTTP غير موثوق → JWT مُتحقق → مستخدم وحالة مؤسسة من DB → TenantContext من المصادقة → permission → organization/ownership → خدمة أعمال.
3. UUID المقدم لا يكفي للترخيص: lookup يجب أن يجمع المعرف مع المؤسسة والأب، ثم نطاق الملكية إن وُجد. هذه نقطة اختبار مستقلة عن إخفاء الزر.
4. مرفق غير موثوق → حدود قراءة وحجم وتوقيع نوع → سجل tenant-owned → تخزين محلي؛ اعتماد فحص التوقيع وحده لا يثبت خلو الملف من المحتوى الضار.
5. بيانات تقرير → Jinja autoescape وCSP → renderer مع تعطيل JavaScript والوصول للشبكات؛ URL للـrenderer من الإعدادات لا من المستخدم.

## C. Findings Register

الأولوية التشغيلية لا تعني أن استغلالًا وقع. التقديرات: S = حتى يومين تقريبًا؛ M = 3–7 أيام؛ L = عدة أسابيع تشمل الاختبارات والتشغيل، وليست التزامًا زمنيًا.

### AUD-01 — CRITICAL — اعتماد Next.js متأثر بتنبيه تنفيذ أوامر على Windows

- **Category / Evidence:** Dependency security؛ `frontend/package-lock.json` يقفل `next=15.5.18`؛ [probes.json](probes.json) يثبت القراءة. [npm-audit-clean.json](npm-audit-clean.json) يسجل 14 package findings: 3 critical، 10 high، 1 moderate، تشمل أدوات تطوير؛ ليست 14 ثغرة قابلة للاستغلال في التطبيق.
- **Affected / Rule:** `frontend/package.json` وlockfile وبيئة بناء/تشغيل Windows. [تنبيه المورّد GHSA-p293-qw3h-jr36](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36) يشمل `>=13.4 <15.5.24` عند التشغيل على Windows filesystem؛ الإعداد الحالي App Router ولا يفعّل Cache Components.
- **Why / Production impact:** حزمة متأثرة مثبتة؛ شروط بيئة Windows المحلية متوافقة مع التنبيه. قابلية استغلال نشر فعلي **Needs Verification**، ولم يُنفّذ exploit. لا يجوز نشر هذه النسخة كما هي.
- **SaaS impact:** اختراق عملية الواجهة قد يؤثر في الجلسات والأنظمة التي تصل إليها.
- **Action / Effort / Urgency:** ترقية أمنية محدودة ومتوافقة وتحديث lockfile ثم build واختبارات وفحص جديد؛ S–M، **P0**. إصدار 15.5.27 مذكور في [إصدار سبتمبر الأمني](https://nextjs.org/blog/september-2026-security-release)، ويجب إعادة فحص التنبيهات وقت الإصلاح. لا يلزم انتقال إلى major جديد. تنبيهات AVIF وSSRF الأخرى تعتمد على تفعيل مساراتها؛ لا يُفترض انطباقها جميعًا.

### AUD-02 — HIGH — بيئة Backend غير مثبتة الإصدار وتحمل مكونات multipart متأثرة

- **Evidence / Affected:** [static-checks.json](static-checks.json): Starlette 0.37.2، python-multipart 0.0.9، FastAPI 0.115.0، Pillow 10.4.0، bcrypt 3.2.2. `backend/pyproject.toml` يطلب Pillow>=11 وbcrypt>=4.0؛ لذلك بيئة الاختبار لا تطابق التبعيات المعلنة. لا lockfile Python متتبع. `pip-check.log` يحوي تعارضات حزم أخرى في المفسر العام؛ ليست كلها تبعيات IORP.
- **Rule / Why:** بناء قابل للتكرار دون مكونات ذات تنبيهات معلومة. [python-multipart advisory](https://github.com/Kludex/python-multipart/security/advisories/GHSA-59g5-xgcq-4qw3) يؤثر في إصدارات أقل من 0.0.18. [Starlette advisory](https://github.com/Kludex/starlette/security/advisories/GHSA-f96h-pmfr-66vw) يشرح استهلاك الذاكرة عند parsing multipart. توجد UploadFile/Form endpoints في shipping وquality وbranding.
- **Production / SaaS impact:** حجب خدمة ومخالفة قابلية إعادة البناء؛ حد `file.read` داخل handler لا يحمي مرحلة parsing السابقة له. التأثر مثبت على مستوى نسخة الحزمة؛ لم تُجر تجربة إغراق.
- **Action / Effort / Urgency:** venv نظيف، حل نسخ FastAPI/Starlette/multipart المتوافقة، lock كامل وفحص supply chain، وحدود ingress/body؛ M، **P0**. فحص pip-audit الكامل **NOT VERIFIED** لأن الأداة غير مثبتة؛ لم أغيّر البيئة لتثبيتها.

### AUD-03 — HIGH — Alembic metadata لا تشمل Master Data

- **Evidence / Affected:** `backend/alembic/env.py:11` يستورد نماذج الوحدات دون `app.masterdata.infrastructure.models`. [probes.py](probes.py) أعاد تشغيل قائمة imports نفسها في مفسر مستقل: **0** جدول Master Data مقابل **5** بعد تحميل التطبيق.
- **Rule / Why:** تطابق schema المراد مقارنته مع نموذج التطبيق. autogenerate قد يقترح حذف جداول منعكسة غير موجودة في target_metadata. هذه مخاطرة مثبتة من عدم اكتمال metadata، وليس ادعاء أن حذفًا حدث.
- **Production / SaaS impact:** هجرة لاحقة قد تزيل تعريفات منتجات كل المؤسسات إذا اعتُمدت آليًا.
- **Action / Effort / Urgency:** استيراد النماذج صراحة واختبار تطابق كامل بين metadata التطبيق وAlembic؛ توليد diff على DB مؤقتة ومراجعته؛ S، **P0 قبل أي autogenerate/نشر هجرة جديدة**.

### AUD-04 — HIGH — Production يسمح ببريد console وتسريب أسرار الاستعادة إلى logs

- **Evidence / Affected:** `backend/app/core/config.py` يضع `email_mode=console`؛ production validator يتحقق من secret وSecure cookie فقط. `core/email/service.py:17` يسجّل text_body/html_body كاملًا. `foundation/application/password_reset.py` و`platform/application/password_reset.py` يضعان رابط reset مع raw token في النص.
- **Rule / Why:** الأسرار المؤقتة لا تُسجّل، ويجب أن تفشل إعدادات الإنتاج غير الآمنة عند البدء.
- **Reproduction:** تجربة Settings بقيم اصطناعية فقط في [probes.json](probes.json) أكدت قبول `production` مع `console email` و`debug=True` معًا؛ لم تُستخدم أسرار تشغيل حقيقية.
- **Production / SaaS impact:** **Confirmed conditional exposure path**: إذا شُغّل production بهذا الوضع، من يستطيع قراءة logs يستطيع قراءة reset link. تشغيل الإنتاج الفعلي بهذا الإعداد **NOT VERIFIED**.
- **Action / Effort / Urgency:** منع console وdebug في production، عدم طباعة أجسام الرسائل أو reset URLs، التحقق من SMTP/TLS وURLs؛ S، **P0 عند استخدام هذا المسار**.

### AUD-05 — HIGH — التعافي والنسخ الاحتياطي غير مثبتين

- **Evidence / Affected:** `docker-compose.yml` يوفر volume PostgreSQL فقط؛ بحث ملفات التشغيل والوثائق لم يجد جدول backup/retention أو restore drill أو RPO/RTO معتمدين. volume ليس backup. لا توجد أدلة تشغيل خارج المستودع مقدمة.
- **Rule / Why:** لا يمكن اعتماد recoverability دون استعادة فعلية، بما فيها المرفقات.
- **Production / SaaS impact:** فقد DB أو uploads قد يكون غير قابل للاستعادة؛ الأثر عالي على كل مؤسسة. وجود نسخ خارج المستودع **NOT VERIFIED** وليس منفيًا.
- **Action / Effort / Urgency:** سياسة نسخ مشفرة ومستقلة، استعادة إلى بيئة منفصلة، مطابقة روابط الملفات وأعداد السجلات، توثيق زمن الاستعادة والفقد الفعلي؛ M، **P1 قبل الإنتاج**.

### AUD-06 — HIGH — بوابة نشر قابلة للتكرار غير مثبتة

- **Evidence / Affected:** لا `.github/workflows` ولا إعداد pipeline أو Dockerfile للتطبيق في الجرد. compose يشغّل DB/renderer فقط، ولا يثبت TLS أو فحص جاهزية أو rollback أو image digest. نجاح اختبارات محلية لا يساوي enforcement. توجد تغييرات كثيرة غير committed، وبعض الهجرات غير متتبعة.
- **Rule / Why:** الإصدار يجب أن يرتبط بمصدر وartifact واختبارات وهجرات قابلة للمراجعة.
- **Production / SaaS impact:** نشر نسخة غير مختبرة أو ببيئة مختلفة، وعدم اكتشاف regression قبل المستخدمين.
- **Action / Effort / Urgency:** pipeline بسيط: install من locks → tests/scans/build → migration rehearsal → artifact version → smoke/readiness → نشر محكوم؛ M، **P1**. CI خارجي محتمل **NOT VERIFIED**.

### AUD-07 — HIGH — سجل التدقيق لا يضمن ذرية الحدث ولا الربط الكامل

- **Evidence / Affected:** `core/interfaces/activity_log.py:49` يستدعي العملية أولًا ثم logger وcommit آخر ويبتلع أخطاء التسجيل. `foundation/application/activity_log.py:19` يستخدم nested transaction ويبتلع الفشل. `core/audit.py:90` ينشئ request context لكن dispatcher لا يمرر request_id/correlation_id إلى سجلات النشاط الجديدة. `backend/docs/AUDIT_LOG_SPEC.md` يصف abort عند فشل التسجيل؛ التنفيذ مختلف.
- **Rule / Why:** عملية حساسة ناجحة يجب ألا تختفي من سجل التدقيق المطلوب؛ وجود Who/What فقط لا يثبت Previous/New/Result/Correlation.
- **Production / SaaS impact:** بعض تغييرات الصلاحيات أو البيانات قد تنجح دون سجل كامل؛ التحقيق والمساءلة غير مضمونين. توجد histories جيدة لعمليات الأعمال، فلا يصح القول إن النظام بلا audit.
- **Action / Effort / Urgency:** تحديد العمليات التي تتطلب audit ذريًا وحفظ الحدث في transaction نفسها، مع before/after آمنين ومعرف request؛ توثيق ما يبقى best-effort؛ M، **P1**.

### AUD-08 — HIGH — التخزين محلي ولا توجد ذرية بين الملف وسجله

- **Evidence / Affected:** `core/storage.py:16` يكتب إلى uploads المحلي. `shipping/application/attachment_service.py:_save` يكتب الملف قبل DB commit بلا تنظيف تعويضي عند فشله؛ remove يحذف سجل DB قبل الملف. startup/config لا يثبتان shared storage.
- **Rule / Why:** اتساق الملفات مع قاعدة البيانات وإتاحة نفس الملفات لكل نسخة تطبيق.
- **Production / SaaS impact:** orphan files عند فشل commit، أو فشل قراءة من replica أخرى؛ الضغط على القرص وحفظ بيانات بعد حذف سجلها. لم يُثبت فقد ملفات فعلي.
- **Action / Effort / Urgency:** سياسة تخزين ونسخ احتياطي وcleanup، staging file ثم تثبيت/تعويض، واختبار crash/restart. shared volume يكفي إذا كان مناسبًا؛ object storage خيار وليس إلزامًا؛ M، **P1 للاتساق وP2 للتعدد**.

### AUD-09 — MEDIUM — عدّاد العينات يتجاوز نطاق own داخل المؤسسة

- **Evidence / Affected:** `backend/app/dashboard/api/routes_dashboard.py:42` يحسب العينات بفلتر المؤسسة فقط. تجربة [probes.json](probes.json): مستخدم samples:read/own؛ `/commercial/samples` total=1 وcommercial dashboard=1، بينما `/dashboard/summary` samples_count=2، كلها HTTP 200.
- **Rule / Why:** aggregates يجب أن تحترم نفس row-level authorization كالقائمة؛ امتلاك read لا يعني organization scope.
- **Production impact:** **Confirmed vulnerability** في كشف إجمالي خارج نطاق الملكية داخل المؤسسة، حتى إن كانت الواجهة الحالية لا ترسم هذا الحقل.
- **SaaS impact:** لم تُثبت cross-tenant exposure؛ الخلل role/scope-level. تجنب تضخيم الوصف.
- **Action / Effort / Urgency:** إعادة استخدام scope المالك عبر provider أو query موحد واختبار مساواة الملخص بالقائمة؛ S، **P0 بوابة إصلاح الترخيص قبل الإصدار**.

### AUD-10 — MEDIUM — حدود الوحدات أقل استقلالًا من المعلن

- **Evidence / Affected:** `quality/application/support.py:21` و`shipping/application/support.py:17` و`procurement/application/support.py:17` تصل مباشرة إلى جداول وحدات أخرى عبر `Base.metadata.tables`. `commercial/application/follow_up_eligibility.py:9` يستورد Foundation models/repository. `core/authorization/scope_resolver.py:15` و`core/audit.py:102` يعكسان اتجاه الاعتماد نحو Foundation/Platform. `dashboard/api/routes_dashboard.py` يجمع نماذج ومستودعات عدة وحدات داخل controller.
- **Rule / Why:** قاعدة `backend/docs/MODULE_BOUNDARIES.md` تقول cross-module عبر protocols. عدم استيراد model لا يلغي الاعتماد على أسماء الأعمدة أو locks في جدول أجنبي. توجد دورة اعتماد على مستوى الحزم Core↔Foundation؛ لم يقع import crash في الاختبارات.
- **Production / SaaS impact:** تغيير schema واحد يؤثر في المستهلكين، وفصل الوحدات مستقبلًا يحتاج نقل المعاملات لا مجرد تغيير import.
- **Action / Effort / Urgency:** سجل استثناءات مقصود للـshared reads/locks، ثم owner-owned read contracts تدريجيًا عند تغيير تلك المسارات؛ لا إعادة كتابة شاملة؛ M–L، **P2**. لم يُثبت في المراجعة write مباشر عابر للوحدات من هذه helpers.

### AUD-11 — MEDIUM — اختلاط حدود Application/API وخدمات واسعة

- **Evidence / Affected:** الجرد رصد 15 موضع import من application إلى API، و18 API→infrastructure imports؛ هذه أعداد مرشحة وليست 33 مخالفة مؤكدة. أمثلة: `commercial/application/order_service.py:16` يستورد request schemas، و`workforce/application/services.py:9`. FoundationService=894 سطرًا؛ CustomerService=671؛ NCRService=455 في snapshot.
- **Rule / Why:** إعادة استخدام حالات الاستخدام تستلزم أنواع input مستقلة عن HTTP؛ حجم الخدمة مع تنوع مسؤولياتها يزيد سطح التغيير. Domain scans لم تجد imports من SQLAlchemy/FastAPI/infrastructure في domain.
- **Production / SaaS impact:** testing وتغيير API أصعب؛ ليست ثغرة ولا سببًا لتقسيم كل class فورًا.
- **Action / Effort / Urgency:** عند تطوير الحالة التالية، فصل input DTO/خدمة ذات مسؤولية واضحة دون مساس بعقود HTTP، وإضافة allowlist للـcomposition؛ M، **P2**.

### AUD-12 — MEDIUM — عمل غير محدود وN+1 جزئي في القراءة

- **Evidence / Affected:** `production/infrastructure/repositories.py:180` يعيد كل orders دون pagination؛ `workforce/api/routes_workforce.py:52` limit اختياري default=None؛ commercial dashboard `_customers/_samples` يسحب الصفوف لحسابها في Python. `commercial/application/sample_service.py:page_samples` يجلب كل مؤلف باستعلام منفصل داخل loop بدل batch؛ الحد 100 يقيد الصفحة ولا يزيل زيادة الاستعلامات بعدد المؤلفين.
- **Rule / Why:** تكلفة الذاكرة/serialization/query count تنمو مع عدد الصفوف؛ ADR-006 مطبق جزئيًا ويصرّح بأن بقية الوحدات لاحقة.
- **Production / SaaS impact:** خطر noisy tenant وزيادة latency؛ **لم يُقَس بطء فعلي أو P95** في هذا التدقيق.
- **Action / Effort / Urgency:** قياس query count وEXPLAIN مع بيانات ممثلة، ثم pagination محدد وSQL aggregation وbatch identity lookup؛ S–M لكل مسار، **P1 لضبط الحدود، P3 لتحسين الفهارس بناء على القياس**.

### AUD-13 — MEDIUM — Rate limiting محلي للعملية

- **Evidence / Affected:** `core/rate_limit.py:8` قاموس `_attempts` وdeque حسب IP/scope، لا shared store؛ تنظيف deque عند الوصول فقط ولا إزالة مفاتيح IP القديمة. يبقى lockout الحساب مخزنًا في DB، فلا يُوصف الحظر كله بأنه مفقود.
- **Rule / Why:** حدود الطلبات يجب أن تُعرّف عبر topology الفعلي، لا worker واحد.
- **Production / SaaS impact:** تزداد الحصة مع عدد workers وتُصفّر عند restart؛ ذاكرة تنمو مع IPs. حمل استنزاف فعلي **NOT VERIFIED**.
- **Action / Effort / Urgency:** حد عند ingress أو تخزين مشترك عند تعدد النسخ، cleanup bounded، واختبار proxy header وسلوك restart؛ S–M، **P1/P2**. Redis ليس مطلبًا مسبقًا.

### AUD-14 — MEDIUM — SMTP متزامن دون timeout أو تسليم موثوق

- **Evidence / Affected:** `core/email/service.py:24` يستخدم `smtplib.SMTP(host, port)` دون timeout. reset services تعمل send قبل commit وتتجاهل Boolean الفشل. `quality/application/capa_notices.py:send_digests` يعيد الإرسال كل تشغيل دون مفتاح dedup يومي.
- **Rule / Why:** الاتصالات الخارجية يجب أن تكون محدودة الزمن وأن تصف دلالات الفشل.
- **Production / SaaS impact:** حجز request/DB transaction، رسالة ناجحة برابط قد لا يُثبت عند فشل commit، أو reset token مخزن دون وصول البريد، أو تكرار digest. لا broker قائم لتوفير DLQ.
- **Action / Effort / Urgency:** timeout، delivery outcome لا يكشف وجود البريد، retry محدود بعد commit مع idempotency؛ persistent outbox صغير عند الحاجة الموثقة؛ M، **P1**. لا retry أعمى لكل عملية إرسال.

### AUD-15 — MEDIUM — استهلاك reset token المتزامن يحتاج إثباتًا

- **Evidence / Affected:** `foundation/application/password_reset.py:execute_reset` ونسخة platform يقرآن `used_at IS NULL` دون `FOR UPDATE` أو claim atomically، ثم يعدلان كلمة المرور ويضعان used_at لاحقًا.
- **Rule / Why:** single-use token يجب أن ينجح مرة واحدة تحت التزامن، لا في طلبين متسلسلين فقط.
- **Production / SaaS impact:** **Likely weakness / Needs Verification**: طلبان متزامنان قد يقبلان نفس token؛ لا نعلن exploit مؤكدًا. ارتفاع token_version قد يتأثر أيضًا بتحديثين متداخلين.
- **Action / Effort / Urgency:** اختبار PostgreSQL بحاجز تزامن؛ إن أعاد طلبان النجاح فاستخدم قفلًا/UPDATE conditional واختبار فائز واحد؛ S، **P1**.

### AUD-16 — MEDIUM — Health غير كافٍ وتشخيص الأعطال جزئي

- **Evidence / Affected:** `main.py:236` يعيد healthy دائمًا؛ `core/db.py:check_database_connection` غير مستخدم في health. `core/logging.py` نص غير structured؛ middleware ينشئ request_id لكن لا يوجد ربط شامل في logs/metrics/traces. تقارير الفشل تسجل code وorganization/duration، وهو إجراء إيجابي.
- **Rule / Why:** liveness ليست readiness، وطلب فاشل أمس لا يُعاد بناؤه دائمًا من السجلات الحالية.
- **Production / SaaS impact:** إرسال traffic لنسخة فقدت DB، وصعوبة تعيين tenant/operation/سبب التأخر. monitoring الخارجي **NOT VERIFIED**.
- **Action / Effort / Urgency:** readiness محدود timeout، structured request logs آمنة مع correlation، مقاييس latency/error/pool/renderer ودليل on-call؛ M، **P1**.

### AUD-17 — MEDIUM — ضمانات SaaS ما زالت تطبيقية ونموذج الهوية محدود

- **Evidence / Affected:** `core/tenancy.py` وrepositories تفرضان organization صراحة؛ لا session-level RLS مبين. FK في كثير من الجداول يربط UUID منفردًا دون قيد مركب يضمن تطابق organization. `foundation/infrastructure/models.py:71` يفرض email فريدًا عالميًا وUser يحمل organization واحدة.
- **Rule / Why:** FK وجود السجل لا يثبت انتماءه لنفس tenant؛ multi-org membership ليس متاحًا في النموذج الحالي. اختيار global email قد يكون مقصودًا، لا خطأ عزل بحد ذاته.
- **Production / SaaS impact:** مسار جديد أو bulk job دون تحقق يمكن أن ينشئ رابطًا غير صحيح؛ مستخدم مؤسسة ثانية بنفس email غير مدعوم. لم تُثبت إمكانية تجاوز tenant عبر API الحالي في الاختبارات المختارة.
- **Action / Effort / Urgency:** ADR للهوية والعضوية، حصر كل access path/child parent/write reference، اختبارات خصمية وجداول استثناءات. قيّم قيودًا مركبة أو RLS حيث تلزم، ولا تضفهما عشوائيًا؛ L، **P2**.

### AUD-18 — MEDIUM — الجلسة آمنة جزئيًا والواجهة بلا مهلة طلب موحدة

- **Evidence / Affected:** `frontend/src/lib/auth.ts` و`platform-auth.ts` يخزنان access tokens في localStorage؛ refresh في cookie HttpOnly. `api-client.ts` يستخدم fetch دون AbortSignal/timeout؛ central refresh موجود ويتجنب طرد المستخدم عند transient failures. `next.config.mjs` لا يضع CSP للتطبيق العام؛ تقارير HTML لديها CSP منفصلة.
- **Rule / Why:** XSS إن وُجد قد يقرأ access token، والطلب المعلق لا يساوي session expired. لم يُعثر على user-controlled dangerouslySetInnerHTML؛ الاستخدام المرصود themeScript ثابت.
- **Production / SaaS impact:** **Hardening recommendation** وليس XSS مثبتًا؛ responsiveness تحت الشبكة البطيئة **NOT VERIFIED**. SameSite=None متاح مع Secure لكن origin/CSRF check لمسارات refresh/logout غير ظاهر؛ يحتاج تحققًا عند cross-site deployment، لا يكفي CORS كمنع CSRF.
- **Action / Effort / Urgency:** سياسة token/CSP مدروسة دون كسر Next inline scripts، timeout/cancel وretry للقراءات فقط، واختبار cookie topology وCSRF؛ M، **P1/P2**.

### AUD-19 — MEDIUM — الأحداث والجداول التاريخية لا تعني تسليمًا أو idempotency عامًا

- **Evidence / Affected:** `shipping/infrastructure/models.py:118` يصف ShipmentEvent كـoutbox لمستهلك مستقبلي، وprocessed_at موجود دون مستهلك نشط مرصود. Production scheduler يستخدم `skip_locked` وإعادة فحص status، وهذا يدعم تعدد العمليات. create APIs لا تحمل عقد Idempotency-Key عامًا؛ histories لا تمنع تكرار إنشاء business document إذا أعاد العميل POST بعد timeout.
- **Rule / Why:** تمييز تسجيل حدث من تسليمه، وتفريق retry انتقال حالة عن retry إنشاء سجل.
- **Production / SaaS impact:** إشعار غير مُرسل أو رسالة مكررة أو أمر مكرر في بعض التدفقات؛ لم يُثبت duplicate عملي هنا. لا حاجة DLQ ما دام لا توجد queue فعلية.
- **Action / Effort / Urgency:** وثّق ما هو غير منفذ؛ اختبر retries وrestarts وduplicates لكل إنشاء حساس، ومفتاح idempotency محدود بالعملية والمؤسسة عند الحاجة؛ M، **P2**؛ إرسال الشحن الآلي **NOT IMPLEMENTED** حاليًا.

### AUD-20 — LOW — فشل fitness test للألوان ووثائق لم تلحق التنفيذ

- **Evidence / Affected:** `frontend/tests/theme-contrast.test.mjs:19` يفترض أن جميع CSS variables معرفة في globals؛ `DashboardWorkspace.tsx` يعرّف `--tone` inline، فيفشل الفحص 5 مرات على المتغير نفسه. 52/53 Node tests نجحت. هذا لا يثبت خلل ألوان بصريًا. `MODULE_BOUNDARIES.md` يذكر policy pass-through بينما dependency الفعلي ScopedAuthorizationPolicy؛ audit spec يصف مخزنًا قديمًا.
- **Rule / Why:** fitness functions والـADRs يجب أن تقيس القاعدة الحقيقية، لا تعطي إنذارًا كاذبًا أو وصفًا مضللًا.
- **Production / SaaS impact:** اختبارات حمراء تضعف الثقة في بوابة النشر؛ وثائق قد تقود تطبيقًا مخالفًا.
- **Action / Effort / Urgency:** دعم scoped/inline variables في الاختبار أو allowlist موثق، ثم تحديث النصوص لمطابقة التنفيذ؛ S، **P1 لبوابة اختبارات خضراء**. لم يُصلح الفشل لأن المهمة تدقيق فقط.

## D. Architecture Characteristics Matrix

| الخاصية | الحالة | الدليل/الحد |
|---|---|---|
| Maintainability | PARTIALLY READY | تقسيم ميزات وقواعد، لكن AUD-10/11/20 |
| Modularity | PARTIALLY READY | protocols واختبارات حدود؛ foreign table reads ومخالفات اتجاه الاعتماد |
| Testability | PARTIALLY READY | SQLite fixtures و682 اختبارًا + PG؛ سيناريوهات failure/كل المسارات ليست كاملة |
| Deployability | NOT READY | dependencies متأثرة، metadata ناقصة، لا بوابة نشر مثبتة |
| Scalability | PARTIALLY READY | DB sessions وlocks؛ uploads وrate limiting محليان |
| Performance | NOT VERIFIED | لا workload ممثل ولا P50/P95/P99 إنتاجية |
| Reliability | PARTIALLY READY | معاملات وحالات وانتقالات؛ SMTP/ملفات/audit بلا اتساق كافٍ |
| Availability | NOT VERIFIED | لا topology/HA أو readiness وتشغيل failover مثبت |
| Security | NOT READY | AUD-01/02/04/09 رغم نجاح اختبارات كثيرة |
| Observability | PARTIALLY READY | request IDs وسجلات أعمال؛ correlation/metrics غير مكتملة |
| Extensibility | PARTIALLY READY | عقود Master Data/Sales جيدة؛ shared-schema coupling |
| Data Integrity | PARTIALLY READY | PG concurrency tests ناجحة؛ metadata وfile transactions وثغرات اختبار متبقية |
| Tenant Isolation | PARTIALLY READY | auth-derived organization واختبارات عدائية؛ لا إثبات لكل access path، وown counter leak |
| Recoverability | NOT VERIFIED | لا restore drill، RPO/RTO أو استعادة uploads مثبتة |

## E. SaaS Gap Analysis

| المرحلة | المطلوب |
|---|---|
| Required before production | AUD-01/02 أمن التبعيات، AUD-03 metadata، AUD-04 secrets/logging، AUD-09 scope؛ ثم backup/restore وrelease gates وaudit/readiness وtimeouts واتساق الملفات |
| Required before SaaS | scope coverage لكل query/write/export/file/job؛ shared storage/rate limits؛ قرارات membership وsupport access، retention/tenant deletion/export، quota لكل مؤسسة، migration rollout واختبار noisy neighbor |
| Recommended as scale grows | SQL aggregation، pagination لبقية القوائم، batch lookups، worker/outbox للبريد إذا لزم، تجارب two replicas وقاعدة البيانات/pool |
| Optional optimization | caching مدروس بمفاتيح tenant/user/scope وإبطال صحيح؛ keyset pagination عند عمق كبير؛ فصل وحدة فقط إذا قياسات الفريق والتشغيل تبرره |

لا حاجة مثبتة حاليًا لـKubernetes أو CQRS أو Event Sourcing أو قاعدة لكل وحدة. المصدر الواحد والـmodular monolith قابلان للاستمرار بعد المعالجة.

### مصفوفة تبديل tenant/resource identifier

| access path | ما يمنع الوصول؟ | الدليل وحدود التحقق |
|---|---|---|
| JWT وtenant context | issuer/audience/type/expiry + organization مطابق للمستخدم + حالة المؤسسة/token_version | `security.py`, `dependencies.py:get_current_user`؛ JWT/tenant tests نجحت |
| Foundation users/roles/profile/logo/logs | tenant من auth، get_by_id_in_organization أو مقارنة current organization | `test_tenant_isolation.py` وسجلات الاختبارات؛ ليست public organization lookup |
| Commercial parents | organization predicate + owner/scope للقراءات المسندة | repositories/visibility؛ تكرار own counter في AUD-09 هو الاستثناء المثبت |
| Samples/evaluations/followups/items | join إلى Customer/parent مصرح ثم child ID؛ incoming org غير مصدر للترخيص | model inventory + route/service tests؛ كل تركيب child ID عبر جميع endpoints **NOT VERIFIED** |
| Production/demands/allocations/results | organization على الجذر ثم parent IDs؛ locks/version للعمليات الحساسة | tenant tests و12 PG tests؛ ليست database-wide RLS |
| Quality/NCR/certificates | org على الجذر، linked order/sample/receipt/return يُقرأ بفلتر مؤسسة | `quality/application/support.py` وservices؛ helpers التابعة تعتمد أحيانًا على IDs الموثوقة من caller، يجب تثبيت precondition |
| Shipping/returns/attachments | org + shipment/return parent على row قبل storage.resolve | `attachment_service.py:_row/file`؛ traversal root check لا يحل محل ownership |
| Procurement/receipts/PO | service org وvalidations للمرجع، ثم child parent | services/support/models reviewed؛ اختبار كل write-reference **NOT VERIFIED** |
| Master Data | `Product.organization_id == self.org`؛ properties تابعة للمنتج | `masterdata/application/services.py`، schema inventory؛ migration metadata منفصلة وخاطئة |
| Reports/export | definition/section permissions + builder scope + حدود rows + no-store | core reporting/customer queries؛ data availability check لا يغني عن authorization |
| Jobs/events | scheduler system-wide مقصود؛ كل order/event يحمل org؛ CAPA يمرر org للـcontacts | لا user-supplied tenant هنا؛ صلاحية job principal ونشر scheduler **NOT VERIFIED** |
| Caches/search | لا search index أو distributed business cache نشط مرصود؛ dashboard state key يشمل identity/permissions | لا يُستنتج من ذلك سلامة CDN أو proxy في نشر غير مفحوص |
| Platform admin | token account_type=platform وnamespace مستقلة، authorized cross-org provisioning | platform tests/route metadata؛ صلاحية تجاوز tenant هنا مقصودة وتحتاج audit موثوقًا |

قاعدة البيانات لا تمنع وحدها كل ربط بين مؤسستين؛ ولذلك اختبار body/query/path IDs المختلفة واجب لكل مسار جديد. ملف inventory يعدد كل route، لكنه **ليس برهان BOLA كاملًا** لكل route.

## F. Performance Baseline

**P50/P95/P99، throughput، capacity، load sensitivity، CPU/RAM/IO under load: NOT VERIFIED.** أزمنة pytest أدناه أزمنة تحقق وليست latency التطبيق. لا استنتاج بأن التطبيق سريع أو بطيء.

أُرفق [load-baseline.js](load-baseline.js) كاختبار k6 **غير منفذ**. خطة قابلة للتكرار:

1. بيئة staging معزولة ببيانات اصطناعية، نسخة build ثابتة، DEBUG=false، workers=2. بداية مرجعية مقترحة: API ‏4 vCPU/8GB، PostgreSQL ‏4 vCPU/16GB وSSD، renderer ‏2 vCPU/4GB؛ سجل المواصفات الفعلية بدل افتراضها.
2. dataset manifests: 10 مؤسسات؛ في كل منها 1k ثم10k ثم100k عميل، وعينتان لكل عميل و5 متابعات وعرضان وأمر واحد. مزيج ownership وحالات ونطاقات زمنية ثابت؛ snapshot قبل كل run. هذه أحجام اختبار مقترحة وليست بيانات البيئة الحالية.
3. fresh token لكل run، warm-up دقيقتان، ثم 5 دقائق لكل concurrency=5/25/50/100 مستخدم. نفّذ script ثلاث مرات لكل حجم/VUS، وأخرج JSON/summary منفصلين. API workload: 70% customers page50،20% samples page50،10% commercial dashboard؛ one-second think time.
4. اختبر PDF منفصلًا عند 1/2/5/10 مستخدم وتقارير 50/500/5000 صف؛ سجّل queue/503/504، وزمن بناء البيانات منفصلًا عن renderer والتنزيل. اختبر الكتابة على disposable tenant فقط مع assertions للآثار والتكرار.
5. اجمع per-endpoint P50/P95/P99 وreq/s/error rate/bytes، وDB query count وEXPLAIN(ANALYZE,BUFFERS)، pool wait، locks، CPU/RAM/IO. افحص load sensitivity بمقارنة زيادة latency مع VUS/الحجم؛ capacity أعلى حمل يحقق SLO متفقًا، لا أعلى throughput مطلقًا.
6. اختبر vertical scale بالموارد المضاعفة ثم horizontal باثنتين من نسخ API على نفس DB/shared storage، مع tenant A صاخب وtenant B صغير. قارن efficiency كـrequests/CPU-second لا مجرد السرعة.
7. responsiveness منفصلة: تحت RTT=200ms وباندويث محدود، قِس ظهور loading state وإمكانية إلغاء الطلب وعرض timeout ومنع duplicate submit. لا تُحوّل عملية مالية إلى async قبل تعريف pending/result semantics.

مثال تشغيل staging: `k6 run --summary-export baseline-25.json -e BASE_URL=https://isolated-staging/api/v1 -e TOKEN=<runtime-token> -e VUS=25 load-baseline.js`. لا تحفظ token في ملف أو سجل. يلزم تثبيت k6 وseed manifest؛ **NOT IMPLEMENTED** كتجربة مقاسة في هذا التدقيق.

## G. Security Findings

| التصنيف | النتائج |
|---|---|
| Confirmed vulnerability / vulnerable component | AUD-09 تسرب count داخل المؤسسة مثبت؛ AUD-01 نسخة Next متأثرة بشرط Windows الموثق؛ AUD-02 نسخ parser متأثرة ومسارات multipart موجودة. استغلال النشر الفعلي لم يُختبر |
| Confirmed conditional exposure | AUD-04 تسجيل reset token عند EMAIL_MODE=console؛ إعداد الإنتاج لا يمنعه |
| Likely weakness | AUD-13 rate-limit متعدد العمليات؛ AUD-15 reset-token concurrency؛ AUD-07 فجوات audit |
| Needs verification | استغلال أي endpoint فعليًا، CSRF مع SameSite=None/topology، malware/polyglot uploads، retention والنسخ المشفرة، tenant isolation لكل query/write/job، dependency audit كامل لـPython وOS images |
| Hardening recommendation | AUD-18 CSP/access-token storage؛ MFA لحسابات المنصة والإدارة الحساسة بعد تحديد نموذج التهديد؛ لا نعد غياب MFA ثغرة مصادقة مثبتة |

SQL المستخدم في الأمثلة المفحوصة parameterized؛ dynamic SQL في migrations بأسماء ثابتة/داخلية لا مدخلات مستخدم. البحث لم يجد مسارًا مؤكدًا لـcommand injection أو unsafe pickle/yaml/eval في كود التطبيق. Jinja يستخدم autoescape، وHTML التقارير CSP، وthemeScript ثابت؛ لا XSS مثبتة. renderer timeout=60s، redirects=false وtrust_env=false، وشبكته معزولة في compose، وهي ضوابط إيجابية ضد SSRF؛ تفعيلها في بيئة إنتاج **NOT VERIFIED**.

فحص الأسرار لم يجد `.env` حقيقيًا متتبعًا ولا توقيعات private-key/AWS/GitHub/Slack ضمن النطاق المحدود. توجد credentials تطوير معلنة في compose/config؛ لا تُعتبر سرًا إنتاجيًا مسربًا دون دليل استخدامها هناك. فحص تاريخ Git وcloud secrets والمحتوى عالي العشوائية **NOT VERIFIED**. لا secret values منشورة في الأدلة.

## H. Technical Debt Register

| النوع | البنود/الدليل | الأثر والاحتمال | الجهد والتوقيت |
|---|---|---|---|
| Accidental | AUD-03،AUD-09 | هجرات خاطئة/aggregate خارج الصلاحية؛ الخلل مثبت | S، P0 |
| Operational | AUD-01/02/04/05/06/08/14/16 | إصدارات متأثرة/فقد أو عدم استعادة/عطل غير مشخص؛ احتمال الإنتاج غير مقاس | S–L، قبل الإنتاج |
| Architectural | AUD-07/10/11/17 | تراكم coupling وضعف حدود الملكية والتدقيق؛ الترابط موجود فعلًا | M–L، تدريجي P1/P2 |
| Intentional | ADR-005 product keys/legacy compatibility؛ ADR-006 offset paging؛ shared DB؛ on-demand reports | خيارات معقولة، لكنها تحد إعادة توليد وثيقة تاريخية واستخراج خدمة | توثيق الاستثناءات، revisit عند نمو متحقق |
| Accidental/operational | AUD-20 وثائق واختبار غير مطابقين | ثقة أقل بالـCI والقرارات | S، P1 |
| Scale-dependent | AUD-12/13/19 | noisy neighbor/حمل متزايد/رسائل مكررة؛ لا saturation مثبت | قياس أولًا، P2/P3 |

لا يُنسب تعمد الدين لفريق التنفيذ ما لم تنص الوثيقة عليه؛ خلط SMTP/storage/audit ليس دينًا مقبولًا تلقائيًا.

## I. Fitness Function Backlog

| Rule / reason | Automation method | Where | Failure condition |
|---|---|---|---|
| لا imports دورية غير مستثناة | AST graph/SCC يشمل imports المحلية وmetadata dependencies؛ allowlist بأسباب | PR CI | دورة جديدة غير مسجلة |
| لا وصول internals لوحدة أخرى | AST import + metadata-table access owner mapping | PR CI | foreign model/repository/table خارج seam معتمد |
| لا Controller→Repository | فحص route modules مع استثناء composition/types فقط | PR CI | استعلام/كتابة persistence في handler غير معتمد |
| لا Domain→Infrastructure/framework | توسيع test_module_boundaries لكل domain | PR CI | import محظور أو relative import يتحايل عليه |
| لا cross-module writes غير مالكة | SQLAlchemy statement capture في contract tests + static metadata update/insert scan | integration CI | عملية تكتب جدولًا لغير مالكها خارج transaction contract موثق |
| لا أسرار متتبعة | scanner مع history baseline ومراجعة false positives؛ لا طباعة قيم | precommit + CI | secret غير مستثنى مع سبب صالح |
| لا ثغرات حرجة غير مقبولة | npm audit وPython scanner على lock وimage SBOM | CI/nightly | advisory reachable critical/high أو exception منتهي |
| لا breaking API غير موثق | OpenAPI snapshot semantic diff + frontend consumer tests | PR CI | حذف/تغيير مطلوب أو enum بلا migration/deprecation |
| لا collection غير محدودة | route contract tests بأكثر من default/max+1 صف؛ SQL LIMIT assertion حيث مناسب | integration CI | default بلا bound أو حد لا يُنفذ |
| tenant/own boundaries محفوظة | tenant-A/B + owner-A/B matrix لكل read/write/child/export/file/dashboard؛ schema inventory يلزم test ID لكل route | CI PostgreSQL | كشف/تعديل بيانات foreign ID، أو totals لا تطابق scope |
| metadata وmigration متطابقان | import parity + disposable PG upgrade head + autogenerate diff reviewed | migration CI | tables ناقصة أو drop غير مقصود أو head متعدد |
| تزامن الأعمال لا يخرق invariant | barrier tests للallocations/results/reset token/counters | PG CI | نجاحان حيث يجب واحد أو تجاوز quantity/version |
| العمليات الحساسة تُسجل ذريًا | fault injection على audit insert مع assert persisted state | integration CI | نجاح mutation المطلوبة للتدقيق دون الحدث |
| جاهزية وتعافٍ قابلان للإثبات | DB-down readiness + restore drill + checksum/count/file validation | staging/release | healthy مع DB غير متاح أو restore/SLO غير محقق |

الموجود اليوم: اختبارات imports/auth namespaces وroute policy catalog وdeny-without-permission وtenancy وبعض PostgreSQL concurrency. المفقود: التنفيذ في CI مثبت، وفحص metadata/كل المسارات والـrestore وdependency gate. success لفحص static policy لا يثبت صحة permission_checked_in_handler؛ يلزم test تنفيذ لكل branch.

## J. ADR Backlog

### ADR مقترح: shared-table reads وملكية المعاملات

- **Context:** بعض الوحدات تقرأ وتقفل جداول غيرها؛ الوثيقة تقول protocol-only.
- **Decision Drivers:** سلامة الإغلاق/الفحص، بساطة monolith، تقليل ترابط schema.
- **Options:** منع تام فورًا؛ عقود قراءة تدريجية؛ views ثابتة مع allowlist.
- **Trade-Offs:** العقود تضيف mapping، والفصل البعيد يفقد transaction المشتركة.
- **Decision المقترح:** owner-owned read/lock contracts ضمن العملية نفسها، واستثناءات مسماة مؤقتة.
- **Consequences:** تغييرات الأعمدة تبقى خلف provider، مع بقاء PostgreSQL واحدة.
- **Fitness Functions:** foreign-table access registry + contract/locking tests.
- **Revisit Conditions:** فريق/نشر مستقل فعليًا أو حمل مقاس يستلزم فصلًا.

### ADR مقترح: هوية المستخدم والعضوية عبر المؤسسات

- **Context:** user.organization_id واحدة وemail عالمي.
- **Decision Drivers:** هل يحتاج الشخص عضويات متعددة، دعم منصة، وفصل صلاحيات كل عضوية؟
- **Options:** إبقاء مؤسسة واحدة؛ حساب عالمي وMembership؛ حسابات منفصلة tenant+email.
- **Trade-Offs:** simplicity مقابل UX وتعقيد token/session والتبديل.
- **Decision المقترح:** إبقاء الحالي للإنتاج الأول وتحديد متطلب multi-org قبل تغيير schema؛ ليس ترحيلًا مصرحًا هنا.
- **Consequences:** لا يُسوّق دعم multi-org identity حتى يُنفذ.
- **Fitness Functions:** login/refresh/org-switch isolation وmembership revocation tests.
- **Revisit Conditions:** عميل فعلي يحتاج أكثر من مؤسسة أو SSO مؤسسي.

### ADR مقترح: ذرية التدقيق ودورة حياة الوثائق والبيانات

- **Context:** histories وسجلات best-effort، وتقارير آنية، وهجرة تزيل report_exports.
- **Decision Drivers:** التحقيق، المتطلبات التعاقدية، الخصوصية، تكاليف الاحتفاظ.
- **Options:** audit ذري لكل شيء؛ ذري للعمليات الحساسة فقط؛ best-effort للجميع.
- **Trade-Offs:** availability عند عطل logging مقابل قابلية الإثبات.
- **Decision المقترح:** قائمة عمليات حساسة fail-closed ذريًا، وسجلات تشخيص best-effort منفصلة؛ تعريف هل الوثائق الصادرة تحتاج snapshot ثابتًا.
- **Consequences:** retention/purge/export/erase لا تعتمد حذفًا عشوائيًا؛ audit سابق لا يعود بمجرد downgrade.
- **Fitness Functions:** audit fault injection + before/after redaction + retention/restore checks.
- **Revisit Conditions:** متطلبات عميل/تعاقد/حجم بيانات جديد.

### ADR مقترح: topology التشغيل والتخزين والتسليم

- **Context:** ملفات محلية، rate limiting ذاكرة، SMTP synchronous، jobs مدمجة.
- **Decision Drivers:** عدد النسخ، RPO/RTO المتفق عليهما، موثوقية الإشعارات.
- **Options:** نسخة واحدة وbackup؛ نسخ عدة وshared storage/ingress limits؛ object store/outbox عند الحاجة.
- **Trade-Offs:** كلفة التشغيل مقابل التوافر؛ لا broker مفروض.
- **Decision المقترح:** وصف topology بسيط مع timeout/readiness/restore ثم توسع بقياس.
- **Consequences:** staging يماثل production وتملك jobs dedup semantics.
- **Fitness Functions:** restart/two-replica/file consistency/rate-limit/restore tests.
- **Revisit Conditions:** قياسات capacity أو متطلبات availability تبرر التوسع.

## K. Remediation Roadmap

| أولوية | عمل محدد | شرط الإغلاق |
|---|---|---|
| **P0 — Release Blockers** | patch آمن للتبعيات المتأثرة AUD-01/02؛ parity لـAlembic AUD-03؛ منع reset secrets في logs AUD-04؛ إصلاح scope AUD-09 | lock قابل للتكرار، scans بلا critical reachable غير معالجة، migration diff صحيح، synthetic log-secret test، own/org totals tests ناجحة |
| **P1 — Before Production** | restore drill؛ CI/release/build؛ audit atomic للعمليات الحساسة؛ files compensation؛ readiness/correlation؛ SMTP timeout؛ اختبار reset concurrency؛ إزالة الفشل الاختباري ووضع default bounds | نتائج staging وfault injection موثقة، RPO/RTO معتمدان ومقاسان، frontend Node+Vitest+build خضراء، migrations rehearsed |
| **P2 — Before SaaS Expansion** | tenant-sensitive path coverage؛ membership decision؛ تخزين/limits متعدد النسخ؛ retention/export/delete؛ contracts بدل foreign internals؛ idempotency للعمليات الحساسة | tests A/B لكل path، two-replica test، تعافي tenant/files مثبت، ADRs معتمدة |
| **P3 — Scale Optimizations** | aggregate queries/batch lookups/indexes/caching/background reports حسب baseline | before/after بنفس dataset/VUS/resources؛ تحسن SLO بلا خطأ حساب/عزل |

ترتيب التنفيذ المقترح: أمن وسلامة بيانات → صحة الأعمال → تعافٍ وموثوقية → حدود معمارية → أداء مقاس → تحسينات صيانة. لا يبدأ refactor واسع تلقائيًا.

## سجل التحقق ونتائج التشغيل

| التحقق | النتيجة | ملف الدليل |
|---|---|---|
| Backend selected auth/tenant/architecture/roles/audit/dashboard suite | **682 passed, 1 warning**, 527.15s | [backend-tests.log](backend-tests.log) |
| PostgreSQL allocations/concurrent transitions/results/close/downtime + selected migrations | **12 passed**, 101.31s | [postgres-bounded-tests.log](postgres-bounded-tests.log) |
| PostgreSQL result/execution/reporting migrations | **11 passed**, 112.16s | [postgres-migrations.log](postgres-migrations.log) |
| Frontend Vitest | **29 files, 191 passed**, 81.30s | [frontend-tests.log](frontend-tests.log) |
| Frontend Node tests | **53 total, 52 passed, 1 failed**، 6.59s | [frontend-node-tests.log](frontend-node-tests.log) |
| TypeScript noEmit، incremental=false | **PASS**, exit 0 | [typescript.log](typescript.log) |
| npm audit | **FAIL** كأمن dependencies: 14 package findings، exit 1 | [npm-audit-clean.json](npm-audit-clean.json) |
| pip check | **FAIL** في المفسر العام؛ ليس كل تعارض من IORP | [pip-check.log](pip-check.log) |
| Alembic heads | head وحيد `f6a1b2k9` | قراءة CLI؛ لا يثبت تطابق DB الفعلي أو سلامة السلسلة |
| targeted reproductions | own count leak وmetadata omission مثبتان | [probes.py](probes.py)،[probes.json](probes.json) |
| secret signatures/current tracked .env | لا matches ضمن هذا الفحص المحدود | [static_checks.py](static_checks.py)،[static-checks.json](static-checks.json) |
| production build / authenticated browser E2E / full backend suite | **NOT VERIFIED في هذا التدقيق** | Vitest/typecheck ليست بديلًا عنها |
| load/chaos/full fresh migration/backup restoration | **NOT VERIFIED** | خطة F وfitness backlog |

ملاحظات التشغيل: أول محاولة npm audit اصطدمت بقيود cache/network؛ أُعيدت بcache محلي ونجحت عملية الفحص وأعادت نتائج ثغرات، لا فشل اتصال. أول تشغيل PG المختلط أوقف بعد انتظار دون نتيجة قابلة للاعتماد؛ أعيدت الاختبارات بمهلة اتصال محددة وسجلات منفصلة. لا نعد المحاولة الموقوفة نجاحًا أو فشلًا وظيفيًا. تحذير Pydantic `validation_alias` في مجموعة backend محفوظ في السجل؛ يحتاج فحص توافق alias على sample payload، ولا يُحوّل إلى failure بلا إثبات.

أوامر إعادة الاختبارات من backend (مع venv صحيح وDEBUG=false):

```text
python -m pytest -q tests/test_all_route_authorization.py tests/test_module_boundaries.py tests/test_authorization_architecture.py tests/test_tenant_isolation.py tests/test_permission_scopes.py tests/test_jwt_token_architecture.py tests/test_password_reset.py tests/test_sensitive_action_permissions.py tests/test_rbac_decisions.py tests/test_system_roles.py tests/test_tenant_audit.py tests/test_platform_audit.py tests/test_department_dashboards.py
python ../docs/audits/2026-10-08/inventory.py
python ../docs/audits/2026-10-08/probes.py
```

PG يحتاج RUN_POSTGRES_TESTS=1 وPGCONNECT_TIMEOUT=5 وقاعدة اختبار مسموحًا فيها بإنشاء schemas المؤقتة؛ fixtures المذكورة تستخدم أسماء test_* UUID وتحذف schemas الخاصة بها. لا تشغّل الهجرات التجريبية مباشرة على جداول الأعمال.

## Final Gate — إجابات مستقلة بالأدلة

| السؤال | الجواب المدعوم |
|---|---|
| هل المعمارية متماسكة داخليًا؟ | **جزئيًا**: monolith بقواعد وعقود مفيدة؛ AUD-10/11 انحرافات dependency وshared-table |
| هل النشر الإنتاجي آمن تقنيًا الآن؟ | **لا يمكن اعتماده**: AUD-01/02/03/04/09 وموانع التشغيل P1 |
| هل ضوابط الأمن الحرجة verified؟ | **جزئيًا**: 682 اختبارًا مختارًا، لكن dependencies وscope defect وبقية gaps تمنع إعلان التحقق الكامل |
| هل ملكية البيانات واضحة؟ | **غالبًا اسميًا وكتابيًا**: inventory 92 جدولًا؛ foreign reads/locks والمعاملات المشتركة AUD-10 تحتاج عقودًا أو استثناءات موثقة |
| هل tenant isolation آمن أو قابل للإدخال؟ | **موجود وقابل للتقوية**: auth-derived org + predicates واختبارات؛ سلامة كل path **NOT VERIFIED**؛ own leak مثبت |
| هل الأداء مقاس؟ | **NOT VERIFIED**: لا benchmark ممثل؛ خطة F وscript فقط |
| هل يمكن التوسع أفقيًا؟ | **جزئيًا**: DB refresh sessions وPG locks مفيدة؛ uploads/limits وعقد التشغيل AUD-08/13 يجب علاجها قبل الاعتماد |
| هل يمكن تشخيص الأعطال؟ | **جزئيًا**: histories/logs/request ID؛ لا correlation شامل أو metrics مثبتة AUD-07/16 |
| هل يمكن التعافي من الأعطال؟ | **NOT VERIFIED تشغيليًا**: transactions وretries محدودة لا تثبت disaster recovery؛ AUD-05/08/14 |
| هل backups قابلة للاستعادة فعليًا؟ | **NOT VERIFIED**: لا restore evidence مقدمة أو منفذة |
| هل تتطور الوحدات دون coupling غير مضبوط؟ | **جزئيًا**: Master Data/Sales contracts جيدة؛ metadata/direct imports AUD-10/11 تحد الاستقلال |
| هل القواعد المعمارية قابلة للتنفيذ آليًا؟ | **نعم جزئيًا بالفعل**: boundary/deny/catalog tests نجحت؛ backlog I يحدد المتبقي؛ CI enforcement غير مثبت |
| ما الذي يمنع Production-ready اليوم تحديدًا؟ | dependencies متأثرة، metadata ناقصة، config قد يسجل reset token، scope count leak، audit/storage/recovery/release/readiness gaps؛ لا يكفي PASS للاختبارات المختارة |
| ما الذي يمنع SaaS-ready اليوم تحديدًا؟ | ما سبق + tenant path completeness، topology/quotas/shared state، identity/membership/retention decisions، تجربة noisy neighbor وrestore وtwo replicas |

## تغطية بقية متطلبات الطلب

- **API contracts:** /api/v1، Pydantic schemas، permission-dependent allowed actions؛ API layer أحيانًا يعيد strings وأحيانًا structured details، والتوحيد غير كامل. pagination مختلط بين page envelope وlist/limit؛ OpenAPI breaking-change gate غير موجود بالدليل. لا يُكشف ORM مباشرة كعقد عام في الأمثلة reviewed؛ application تستورد API DTOs (AUD-11).
- **Transactions/indexes/deletion:** inventory يسجل indexes/constraints/FKs؛ لا نستنتج فعالية index دون EXPLAIN. بعض المعاملات جيدة تحت PG، وبعض الخدمات commit داخليًا وaudit بعده. حذف العينات يحذف evaluations، وغيرها تستخدم deactivate/final statuses؛ لا سياسة lifecycle واحدة موثقة لكل البيانات. report_exports migration تحذف السجل وتعيد جداول فارغة في downgrade؛ downgrade ليس استعادة بيانات.
- **Migrations:** f6a1b2h5 يرفض حذف legacy outputs إذا بقيت rows/references؛ هذا guard إيجابي. f6a1b2i4 يزيل report audit عمدًا؛ أثر retention يجب اعتماده. اختبارات أجزاء السلسلة لا تثبت fresh base→head أو كل downgrade، خصوصًا migrations الجديدة غير المتتبعة.
- **Responsiveness/background:** PDF synchronous لكن DB read transaction تُحرّر قبل renderer؛ timeout=60s وqueue bound في compose. لا داعي async لكل تقرير؛ اختبر الضغط وحدد متى يتحول إلى job. SMTP أول مرشح لتحديد timeout/durable delivery بعد تعريف semantics.
- **AI/LLM:** `backend/app/ai/__init__.py` فقط في جرد الوحدة؛ لا provider/prompt/tool/model workflow نشط عُثر عليه. AI readiness غير منفذة، وليست فشلًا لميزة موجودة. **NOT IMPLEMENTED**: AI evaluation/cost controls/tool approvals لأنها خارج النظام الحالي.
- **Frontend:** feature folders، apiClient موحد، next-intl، permission-aware controls، session guard واختبارات؛ enforcement الحقيقي backend. لا bundle-size measurement أو accessibility/browser E2E جديد؛ **NOT VERIFIED**. صور/اختبارات قديمة لا تُحتسب لهذا التدقيق.
- **External failure design:** لا remote A→B→C→D workflow للأعمال مرصود؛ renderer وSMTP هما الحدّان الأساسيان. لا generic retry للمبيعات مطلوب دون idempotency. circuit breaker لا يضاف دون دليل حاجة.
- **Technology health:** التنبيهات الحالية موثقة أعلاه؛ لم يُفحص كامل Python transitive graph ولا OS/container SBOM ولا دعم كل إصدار من مصادره، وبالتالي **NOT VERIFIED** ولا توصية ترقية لمجرد وجود نسخة أحدث.

**توقف التدقيق هنا. لم تُنفذ الإصلاحات أو إعادة الهيكلة. يلزم اعتماد نطاق معالجة محدد؛ الخطوة المقترحة تبدأ بـP0 مع baseline واختبارات قبل/بعد.**
