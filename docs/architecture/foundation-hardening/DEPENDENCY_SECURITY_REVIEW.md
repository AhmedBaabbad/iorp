# مراجعة أمن الاعتماديات — IORP

**التاريخ:** 2026-10-14 · **الطريقة:** `npm audit --json` للقراءة فقط على السجل الرسمي. لم تُطبَّق أي ترقية.

## التحقق قبل الإرسال الخارجي
- لا يوجد `.npmrc` في المشروع ولا في مجلد المستخدم؛ السجل `https://registry.npmjs.org/`.
- كل الحزم الـ547 في `package-lock.json` مصدرها `registry.npmjs.org`؛ **لا حزم خاصة**؛ لا بيانات اعتماد أُرسلت.

## الملخص
**الواجهة:** 14 حزمة متأثرة: **2 critical، 10 high، 2 moderate**. **لا شيء منها في مسار تنفيذ الطلبات في الإنتاج بشكل قابل للاستغلال بالدليل الحالي.** المؤثر على الإنتاج حزمتان بنطاق بناء/تحسين صور، والباقي أدوات تطوير. **الخلفية:** 5 حزم؛ الأهم Starlette (حدود multipart) ويتطلب إصلاحها ترقية رئيسية.

## 1. ما يُشحن مع التطبيق (`npm ls --omit=dev`)
| الحزمة | النسخة | التنبيهات | قابلية الاستغلال في IORP | الإصلاح الموصى |
|---|---|---|---|---|
| `next` | 15.5.27 | moderate عبر postcss | غير مباشر (انظر postcss) | تجربة `next@15.5.28` (متاحة، نفس الإصدار الرئيسي) وإعادة الفحص؛ الإصلاح الكامل المقترح من npm هو `16.4.1` (**major** — لا يُطبَّق دون خطة) |
| `postcss` (داخل next) | 8.4.31 | GHSA-qx2v-qp2m-jg93 (XSS في الإخراج)، GHSA-6g55-p6wh-862q، GHSA-fxqj-rqcc-2cmp، GHSA-r28c-9q8g-f849 (قراءة ملفات .map عبر `sourceMappingURL`) | **منخفضة**: يعمل وقت البناء على CSS المشروع نفسه؛ لا CSS من المستخدمين | `overrides: { "postcss": "^8.5.23" }` مع build كامل، أو ترقية next |
| `source-map-js` (داخل postcss) | 1.2.1 | GHSA-68fv-2mgg-jv7q (DoS) | **منخفضة**: وقت البناء فقط | يُصلح مع postcss |
| `sharp` (داخل next) | 0.34.5 | ثغرات libvips/libheif/librsvg (GHSA-f88m-g3jw-g9cj، GHSA-rgj7-g3m4-5g8c، GHSA-wq5f-xc86-pv6w) | **منخفضة**: الكود لا يستخدم `next/image`؛ لا `images.remotePatterns`؛ لكن مسار `/_next/image` مفعّل افتراضيًا للصور المحلية | `images: { unoptimized: true }` في `next.config.mjs` يعطّل المحسّن كليًا (تغيير صغير بلا أثر وظيفي لأن `next/image` غير مستخدم)، أو ترقية sharp عبر override |

## 2. أدوات التطوير فقط (لا تُشحن)
| الحزمة | الشدة | الاستغلال | الإصلاح |
|---|---|---|---|
| `vitest` 3.2.x، `tinypool` | **critical** (GHSA-5gmw-xhrv-c9v3، GHSA-85c8-ppgw-ccpr: prototype pollution → RCE في خيارات العامل؛ GHSA-82fw-gwwq-j7x9 قراءة ملفات عبر mocker) | يتطلب تحكمًا بإعدادات/ملفات الاختبار نفسها على جهاز المطوّر أو CI | `vitest@5.0.4` (**major**) أو override لـ `tinypool@>=2.1.2` إن توافق؛ مع تشغيل كل اختبارات الواجهة |
| سلسلة eslint: `eslint-config-next` → `@next/eslint-plugin-next` → `fast-glob` → `micromatch` → `braces`؛ و`brace-expansion`، `js-yaml` | high (DoS بأنماط glob/YAML مصممة) | أنماط وملفات المشروع نفسه؛ لا مدخلات خارجية | ترقية `eslint-config-next` إلى إصدار يطابق next، و`npm audit fix` غير الكاسر لـ brace-expansion/js-yaml |

## 3. Python (`pip-audit` على البيئة المعزولة المطابقة لـ `pyproject.toml`)
| الحزمة | النسخة | التنبيه | قابلية الاستغلال في IORP | الإصلاح |
|---|---|---|---|---|
| `starlette` | 0.52.1 | PYSEC-2026-249 (حدود `max_fields/max_part_size` في `request.form()` لا تُطبَّق كاملة) | **متوسطة**: توجد مسارات رفع ملفات multipart (الشحن، الجودة، الشكاوى، الهوية) — خطر استهلاك موارد | يتطلب Starlette ≥1.3.1 ← يتطلب FastAPI يدعم Starlette 1.x؛ `pyproject.toml` يقيّد `<1.0` — **تغيير رئيسي يحتاج خطة**. تخفيف مؤقت: حد حجم الجسم في الـreverse proxy |
| `starlette` | 0.52.1 | PYSEC-2026-161، PYSEC-2026-248 (إعادة بناء `request.url` من ترويسة Host دون تحقق) | **منخفضة**: الكود لا يستخدم `request.url` ولا `url_for`؛ روابط البريد تُبنى من `FRONTEND_URL` في الإعدادات | مع الترقية؛ + `TrustedHostMiddleware` أو ضبط Host في الـproxy |
| `starlette` | 0.52.1 | PYSEC-2026-2281 (StaticFiles على Windows)، PYSEC-2026-2280 (HTTPEndpoint) | **غير قابلة للوصول**: لا `StaticFiles` ولا `HTTPEndpoint` في الكود | مع الترقية |
| `python-jose` | 3.5.0 | CVE-2026-85394 (قبول مفاتيح عامة غير مغلّفة في تهيئة HMAC — key confusion) | **منخفضة**: الخوارزمية مثبتة `HS256` (`core/security.py:38`) ومفتاح سري من الخادم؛ لا مفاتيح يقدمها العميل | لا إصلاح منشور؛ الاستبدال بـ PyJWT خيار لاحق |
| `ecdsa` | 0.19.2 | PYSEC-2026-1325 (Minerva timing على P-256) | **غير قابلة للوصول**: تبعية غير مباشرة لـ jose؛ لا توقيع ECDSA في IORP | — |
| `pytest` | 8.4.2 | PYSEC-2026-1845 (DoS محلي على `/tmp/pytest-of-*` في UNIX) | أداة تطوير | `pytest>=9.0.3` |

**ملاحظة:** البيئة العامة المستخدمة سابقًا أسوأ (Starlette 0.37.2، python-multipart 0.0.9 — AUD-02).

## 4. التوصية (للدفعة 4 — لا تُطبَّق الآن)
1. `next` → 15.5.28 + override لـ postcss + `images.unoptimized` ← build + اختبارات كاملة.
2. vitest → 5.x في فرع منفصل مع إصلاح أي اختبارات تنكسر.
3. eslint-config-next متوافق مع next.
4. إدراج `npm audit --omit=dev --audit-level=high` و`pip-audit` في CI كبوابة.
