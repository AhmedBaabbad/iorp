# مصفوفة الاختبارات والقبول

2026-10-14. اختبارات الجولة تستخدم fixtures SQLite مؤقتة في backend/tests/conftest.py، مع DEBUG=false وEMAIL_MODE=console. لا اختبارات هجومية على المنظمات الحقيقية ولا إرسال بريد فعلي.

## التشغيل الحالي

الأمر: python -m pytest tests/test_tenant_isolation.py tests/test_platform_isolation.py tests/test_jwt_token_architecture.py tests/test_readiness_transactions.py -q --tb=no --disable-warnings

النتيجة الفعلية: **127 passed, 2 failed in 138.30s**، ورمز خروج الاختبارات 1. المجموعة ليست ناجحة بالكامل.

الاختباران الفاشلان:

1. `test_write_mutations_return_404_for_cross_tenant_resources[post-/api/v1/admin/users/{id}/lock-user_b-None]` في `backend/tests/test_tenant_isolation.py:180`: الاستجابة **422 بدل 404**. الطلب لا يرسل سبب القفل الذي أصبح إلزاميًا؛ لذلك يفشل التحقق من المدخلات قبل الوصول إلى اختبار ملكية المورد. يلزم لاحقًا إرسال سبب صالح للتحقق من رفض المورد الأجنبي، مع اختبار مستقل لإلزام السبب. لا يكفي تغيير التوقع إلى 422.
2. `test_organization_id_in_body_ignored_on_user_update` في الملف نفسه، السطر 273: الاستجابة **422 بدل 200**. يرسل الاختبار `full_name` و`organization_id` مزورًا، بينما العقد الحالي يرفض الحقول الإضافية ويمنع التعديل الإداري للبيانات الشخصية. يلزم تحديث الاختبار وفق السياسة الحالية والتأكد من بقاء المنظمة والقيم المحفوظة دون تغيير؛ لا تخفيف الحماية لإرضاء التوقع القديم.

أعيد تشغيل الاختبارين فقط باستخدام `--tb=line`: **2 failed in 3.96s**، وأكدت المخرجات `assert 422 == 404` و`assert 422 == 200`. لا يمثل الفشلان دليلًا مثبتًا على تسرب بين المنظمات، ولا يثبت نجاح الاختبارات الأخرى شمول العزل لجميع المسارات. لم تعدل الاختبارات أو التطبيق في هذه الجولة التزامًا ببوابة الموافقة.

| مجال | الدليل الحالي | القبول المطلوب قبل الإطلاق |
|---|---|---|
| قراءة/تعديل/حذف أجنبي | test_tenant_isolation.py؛ عملاء، مستخدمون، أدوار، متابعات، workforce، إنتاج وجودة | تعميم على كل endpoint مملوك، opaque 404/403 بلا payload أجنبي وتأكيد عدم تغير DB. |
| تزوير المنظمة | اختبارات body/query في الملف نفسه | إضافة headers/path وتقرير/ملف وتأكيد tenant server context. |
| تصعيد أفقي/رأسي | test_platform_isolation.py، اختبارات scopes موجودة خارج تشغيل الجولة | tenant token إلى Platform والعكس، حساب محدود إلى action حساس؛ فحص HTTP والبيانات. |
| JWT | test_jwt_token_architecture.py | issuer/aud/type/expiry وrefresh replay؛ اختبار access replay بعد logout للمنصة مطلوب، لا يكفي فحص refresh. |
| audit transactions | test_readiness_transactions.py | اختبارات عامة لا تثبت atomicity لمسار انتقال المنظمة؛ إضافة fault injection خاص به والحصة والإنشاء. |
| ملفات وتقارير | test_file_policy.py ومجموعات commercial/quality/production reporting موجودة ولم تشغّل هنا | تنزيل وتصدير resource أجنبي، مسار غير صالح، quota، تخزين داخل tenant، عدم leak في errors. |
| MFA | غير منفذ | enrollment/recovery/replay/brute force وreset/refresh bypass، لا رموز كاملة قبل challenge. |
| DB constraints/RLS | مراجعة schema فقط | PostgreSQL disposable لا SQLite وحده، FK عابر وتزامن وانتقالات rollback. |
| Migration | لم تنفذ أي migration في الجولة | fresh upgrade + بيانات اختبار قديمة + recovery plan لكل تعديل لاحق. |
| Backup/restore | NOT VERIFIED | بيئة كاملة مع DB/files؛ قياس RPO/RTO؛ رفض الإنتاج كهدف استعادة. |
| Production/sales/CRM/inventory/reporting | لم تشغل كامل suites | regression حسب تأثير كل حزمة؛ لا ادعاء نجاح شامل لهذه الجولة. |
| CI/CD | غير مثبت | job واضح للعزل والمصادقة والتدقيق وmigration، يمنع الدمج عند فشل P0. |
| Dependency/security config | إعدادات موجودة وتدقيق قديم فقط | فحص حديث مؤرخ وملف نشر واقعي؛ لا تشغيل production config في قاعدة الاختبار. |
| أداء | N+1/unbounded ثبتا من الكود، لا قياس load | قياس queries لكل صفحة والذاكرة والزمن قبل/بعد، دون وعود أرقام غير مقاسة. |

## التعامل مع الفشل

الفشل لا يُخفى. يسجل اسم الاختبار وعدد الناجح والفاشل دون رموز دخول أو بيانات حساسة. بعض التوقعات قد تتعارض مع سياسة الحسابات الجديدة؛ يجب التأكد من persisted values ومن رفض override، لا تعديل assertions عشوائيًا. تبقى المجموعة غير خضراء حتى الإصلاح بعد الموافقة.
