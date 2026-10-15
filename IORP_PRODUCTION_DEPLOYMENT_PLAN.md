# IORP — خطة الجاهزية والنشر الآمن

تاريخ الفحص: 2026-10-15. النطاق: اكتشاف المستودع فقط. لم يُتصل بالـVPS، ولم تُعدّل الشيفرة أو بيانات التشغيل، ولم تُشغّل عمليات نشر أو ترحيل. هذا الملف هو المخرج الوحيد لهذه المهمة.

**القرار:** المشروع يحتوي مكونات تشغيل وحماية واستعادة قابلة لإعادة الاستخدام، لكنه ليس حزمة نشر إنتاجية مكتملة بعد. نكمل خمس مراحل متتابعة؛ لا نعيد تصميم تعدد المنظمات أو المودلات. أرقام الاختبارات السابقة ليست إثباتًا لصحة نسخة العمل الحالية: لم تُعد الاختبارات أو عملية build خلال هذا الفحص.

## ما ثبت من المستودع

| المجال | الدليل الفعلي | الاستنتاج |
|---|---|---|
| الواجهة | `frontend/package.json`، `frontend/package-lock.json`، `frontend/next.config.mjs` | Next.js `~15.5.27` وReact 19؛ `next build` ثم `next start`. تحويل `/api/v1` إلى `BACKEND_URL` يحافظ على نفس نطاق المتصفح. لا يوجد إعداد standalone حاليًا. |
| الخادم | `backend/pyproject.toml`، `backend/app/main.py` | FastAPI/Uvicorn؛ نقطة التشغيل `app.main:app`؛ Python ≥3.10 واعتماديات بنطاقات إصدارات. يلزم اختيار إصدار runtime وتثبيت اعتماديات Linux القابلة للتكرار. |
| الحاويات | `docker-compose.yml` | يشغّل PostgreSQL 16 وGotenberg 8.37.0 وبوابة Nginx فقط؛ لا Dockerfiles للتطبيق ولا Traefik ضمن الإعداد الحالي. كلمة مرور PostgreSQL مثال تطوير، والمنفذ مربوط بـloopback. ليس إعداد إنتاج. |
| التقارير | `backend/app/core/reporting/renderers.py`، `backend/app/core/reporting/nginx.conf` | بوابة تسمح بمسار تحويل HTML فقط، وعزل renderer مع منع JavaScript والوصول للشبكات العامة والخاصة. يجب الحفاظ على الحماية والخطوط العربية. |
| البيانات | `backend/app/core/db.py`، `backend/alembic/env.py`، `backend/alembic/versions/` | SQLAlchemy وAlembic؛ فحص اتصال محدود الزمن؛ جداول تاريخية مستثناة من حذف autogenerate. يلزم اختبار سلسلة migrations على PostgreSQL، وليس ORM create_all وحده. |
| المرفقات | `backend/app/core/storage.py`، `backend/app/core/config.py` | LocalFileStorage تحت `UPLOADS_DIR`، ومفاتيح تتضمن المنظمة؛ البيانات الثنائية خارج PostgreSQL. فقدان volume يفقد الملفات ولو بقيت قاعدة البيانات. |
| الهوية والعزل | `backend/app/dependencies.py`، `backend/app/core/tenancy.py`، `backend/app/core/security.py` | سياق منظمة من الهوية، فحص token_version والجلسات، رفض الإشارات العابرة للمنظمات. لا تعني قراءة هذه الملفات تدقيق كل مسار من جديد. |
| حماية التشغيل | `backend/app/core/config.py`، `backend/app/core/middleware.py`، `backend/app/main.py` | ضوابط production للـHTTPS والأسرار والكوكيز، إخفاء docs، ترويسات حماية. بعض هذه التغييرات ضمن عمل غير مثبت؛ `staging` لا يفعّل تلقائيًا كل شروط `production`. |
| المهام | `backend/app/production/application/order_scheduler.py`، lifespan في `main.py` | جدولة داخل العملية، اختيارية ومتوقفة افتراضيًا، موصوفة كـidempotent مع قفل الصفوف. لم يظهر نظام queue مستقل؛ لا حاجة لإضافة Redis/Celery لمجرد النشر. |
| الصحة والسجلات | `backend/app/main.py`، `backend/app/core/logging.py` | `/health` للحيوية و`/health/ready` لاتصال DB؛ ليست فحصًا كاملًا للتقارير والتخزين وSMTP. السجلات نصية، مع request ID في middleware، وتحتاج تدويرًا وتنبيهات تشغيلية. |
| النسخ | `backend/scripts/backup/iorp_backup.py`، `backend/scripts/recovery_drill.py`، `docs/operations/BACKUP_AND_RECOVERY.md` | أداة نسخ DB والملفات، تشفير، manifest، وفحص استعادة محمي. لا تثبت وجود جدولة أو نسخة خارجية فعلية على VPS. |
| Git وCI | HEAD=`38bbec7`؛ لا مجلد `.github` في الفحص | تغييرات tracked/untracked، منها MFA وmigration وواجهة؛ ليست إصدارًا مثبتًا. لا workflows محلية؛ خصوصية GitHub وإعداداته الخارجية غير متحققة. |

## أولويات الإغلاق

- **P0 قبل الإنتاج:** إصدار Git مكتمل ومختبر؛ حاويات بناء قابلة للتكرار؛ أسرار مستقلة وإعداد production صحيح؛ عزل الخدمات والمجلدات؛ مراجعة proxy/IP والكوكيز؛ إثبات migrations والاستعادة المشفرة خارج الخادم؛ سعة VPS كافية دون إضرار بالمشاريع؛ اختبارات أمنية ناجحة وبوابة نشر إنتاجية محكومة.
- **P0 شرطي:** أي ثغرة قابلة للاستغلال في اعتماديات الإصدار أو فشل عزل/تفويض يظهر بالفحص يمنع الإصدار. لا يوجد فحص CVE جديد في هذه المهمة، فلا نفترض سلامة الإصدارات أو وجود ثغرة محددة.
- **P1:** سجلات مركزية ومقاييس أعمق، CSP بوضع report-only ثم اختبار التوافق، تحسين تنبيهات الأداء وخطة ترقيات دورية، معالجة قيود rate limiting داخل العملية قبل زيادة replicas.
- **P2:** خادم staging منفصل، إتاحة عالية وتوسّع أفقي أو تخزين object storage عند الحاجة. PITR يصبح P0 إذا كان RPO المعتمد أقصر مما تحققه النسخ المنطقية المجدولة.

## 1. إصلاحات الجاهزية الإنتاجية

**العمل:** حصر التغييرات وملكيتها ثم تثبيت إصدار، بما فيه إغلاق اختبارات MFA والاسترداد قبل أي إلزام. تثبيت Node/Python واعتماديات production؛ إنشاء Dockerfiles متعددة المراحل و`.dockerignore` لا تضم `.env` أو uploads أو نسخ DB. تشغيل backend بدون reload وبمستخدم غير root؛ تشغيل الواجهة بـ`next start` أو standalone بعد اختباره. تضمين قوالب التقارير والخطوط في الصور.

**الملفات:** الموجودة أعلاه، `backend/.env.example`، `frontend/.env.example`، `backend/app/core/rate_limit.py`، `docs/operations/PLATFORM_PRIVILEGED_SECURITY.md`؛ المقترح إنشاؤه لاحقًا: `backend/Dockerfile`، `frontend/Dockerfile`، ملفات تجاهل Docker وقفل اعتماديات backend معتمد. ملف `docs/architecture/foundation-hardening/evidence/python-baseline-lock.txt` دليل سابق يحتاج التحقق على Linux، وليس ضمانًا وحده.

**الخطر P0:** صورة لا تحتوي مصدرًا غير متتبع، أسرار ضمن build، أو proxy يجعل كل العملاء عنوانًا واحدًا/يقبل X-Forwarded-For مزورًا. لا تستخدم `TRUSTED_PROXY_IPS=*`. اختبر السلسلة Traefik → Next → backend وضبط الوكلاء الفعليين؛ إبقاء عملية backend واحدة بدايةً يقلل تشتت limiter، بشرط قبول اختبار الحمل.

**القبول:** clean checkout يبني الصورتين؛ نجاح اختبارات الهوية والعزل وMFA والعربية والإنجليزية؛ ملفات وصور PDF عربية سليمة؛ cookies آمنة واستعادة كلمة المرور برابط HTTPS صحيح؛ جلسات الخمول تنتهي كما صُممت؛ لا تسرب أسرار أو traceback للعميل. ضبط production في staging أيضًا، أو توحيد الضوابط باختبار صريح. **الاعتماد:** لا مرحلة سابقة؛ معلومات نطاقات التشغيل مطلوبة لإكمال القبول.

## 2. مستودع GitHub خاص وCI

**العمل:** التحقق من remote والملكية والخصوصية قبل إنشاء مستودع جديد؛ فحص الأسرار في التاريخ وملفات الإصدار. حماية الفرع وفحوص PR إلزامية. GitHub-hosted runners للبناء والاختبار؛ لا تشغيل كود PR على VPS. `npm ci` واعتماديات Python مثبتة، ثم اختبار وبناء وفحص اعتماديات وصور، ونشر الصور إلى registry خاص بوسم commit وdigest. لا أسرار في NEXT_PUBLIC أو build args.

**الملفات:** `frontend/package-lock.json`، `backend/pyproject.toml` والقفل المعتمد؛ المقترح `.github/workflows/ci.yml` و`deploy.yml`. إعادة استخدام `backend/tests/test_all_route_authorization.py`، `test_authorization_architecture.py`، `test_tenant_isolation.py`، `tests/security/test_cross_tenant_sweep.py` و`test_cross_tenant_additional.py`، واختبارات migrations وMFA وbackup الموجودة، و`frontend/tests/`.

**القبول:** تشغيل كامل backend/frontend حيث أمكن، وتسجيل failures/skips، PostgreSQL معزول وليس اتصال التشغيل، واكتشاف API من التطبيق الحقيقي. build إنتاجي ناجح من commit نفسه، scans بلا مخاطر مانعة غير معالجة، صور يمكن سحبها بالـdigest. تثبيت Actions على commit SHA وصلاحيات GITHUB_TOKEN الدنيا. منع deploy متزامن بـconcurrency.

**الخطر P0:** نشر تغييرات غير مثبتة أو تسريب credentials أو افتراض توفر required reviewers لمستودع خاص. توفر حماية environments يعتمد على خطة GitHub؛ إن لم تتوفر، نعتمد تشغيل نشر يدوي بواسطة مسؤول مخوّل مع سجل إصدار وصلاحية نشر مقيدة، دون الادعاء بوجود فصل موافقات غير مفروض. [توثيق GitHub](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).

**الاعتماد:** المرحلة 1؛ معلومات حساب GitHub وخطته وregistry. لا push أو إنشاء remote ضمن مهمة الاكتشاف.

## 3. Staging على Hostinger VPS المشترك

**العمل:** جرد read-only مصرح به أولًا؛ إعادة استخدام مدخل Traefik الحالي إن وجد. لا إنشاء مدخل ثانٍ ينازع 80/443، ولا تغيير إعدادات مشاريع أخرى. إنشاء مشروع Compose باسم `iorp-staging` وموارد محدودة بعد قياس المتاح، بيانات اصطناعية وبريد اختبار دون مراسلة عملاء.

**التصميم المقترح:** الإنترنت → Traefik TLS → frontend:3000 → backend:8080 → PostgreSQL:5432؛ backend → report-gateway:80 → Gotenberg:3000. لا نشر منافذ DB/backend/renderer على المضيف. `BACKEND_URL=http://backend:8080` ثابت داخل صورة Next عند build والتحقق من rewrite؛ يبقى اسم الخدمة نفسه في البيئتين فتُرقّى الصورة نفسها. `REPORT_RENDERER_URL=http://report-gateway`.

- شبكة ingress مخصصة لـIORP تربط Traefik والواجهة فقط قدر الإمكان؛ شبكة تطبيق تربط الواجهة والخادم؛ شبكة DB للخادم وPostgreSQL فقط؛ شبكة renderer الداخلية تبقى منفصلة. السماح بخروج backend اللازم لـSMTP دون جعل DB مكشوفة.
- عدم ربط مشاريع VPS الأخرى بشبكات DB، وتحديد شبكة Traefik صراحةً وتسميات routers فريدة. تعريض الخدمات باختيار صريح فقط؛ أي تعديل عالمي لـTraefik يسبقه فحص تأثيره على المشاريع الحالية.
- production مشروع مستقل `iorp-production` مع DB وأسرار وvolumes ونطاق مستقل؛ لا مشاركة uploads أو بيانات الدخول أو مفاتيح JWT/MFA بين البيئتين. نفس المضيف يعني اشتراكًا في خطر انقطاعه أو امتلاء قرصه.
- volumes ثابتة منفصلة لـPostgreSQL وuploads، وضبط `UPLOADS_DIR=/var/lib/iorp/uploads`؛ mount قابل للكتابة للـbackend فقط حسب الحاجة. حماية تخزين شهادات Traefik الموجود وعدم استبداله.
- لا docker.sock داخل التطبيق. إبقاء لوحة Traefik إدارية وغير عامة. healthchecks، restart policy، log rotation وحدود ذاكرة/CPU خاصة بالتقارير؛ لا أرقام سعة نهائية قبل الجرد.

**الملفات:** إعادة استخدام `docker-compose.yml` و`backend/app/core/reporting/nginx.conf`؛ المقترح `compose.deploy.yml` وملف إعداد Traefik مخصص لـIORP حسب تنظيم VPS الفعلي، لا استبدال Compose التطوير.

**القبول:** HTTPS وتجديد شهادات، منع الوصول المباشر للخدمات، عدم وصول staging إلى DB الإنتاج، اختبار spoofed forwarding headers والرفع والتنزيل وPDF وSMTP التجريبي، إعادة إنشاء الحاويات دون فقد الملفات، وتحميل ممثل دون تدهور المشاريع القائمة. **الخطر P0:** تضارب ports/شبكات/موارد. **الاعتماد:** 1 و2 والجرد المذكور أدناه.

## 4. PostgreSQL والترحيلات والنسخ والتعافي

**العمل:** PostgreSQL 16 خاص بكل بيئة بدايةً، صورة بإصدار مصحح محدد وdigest بعد الاختبار. حساب مالك/ترحيل منفصل عن حساب التطبيق الأقل صلاحية، واختبار grants وdefault privileges للـtables/sequences. حساب نسخ بصلاحيات القراءة اللازمة؛ لا استخدام superuser كحساب التطبيق.

تشغيل `alembic upgrade head` كـjob واحد من صورة backend الإصدارية قبل استقبال المرور، مع قفل تسلسلي للنشر. لا migration تلقائية عند بدء كل replica. اختبار قاعدة فارغة ونسخة ممثلة للإصدار السابق، ثم فحص revision وسلامة العلاقات. لا downgrade تلقائي ولا autogenerate على الإنتاج.

**النسخ:** إعادة استخدام `iorp_backup.py`، جدولة مشفرة إلى وجهة خارج VPS بحساب مستقل واحتفاظ محمي؛ تشفير الحزمة الخارجية كاملة بما فيها manifest الذي قد يحتوي أسماء ملفات وبيانات وصفية. تخزين مفتاح فك النسخ وأسرار JWT/MFA اللازمة للاستعادة في مخزن منفصل قابل للاسترداد. مزامنة DB والملفات بنافذة منع كتابة قصيرة تشمل scheduler والمهام؛ snapshot قاعدة البيانات وحده لا يضمن اتساق الملفات.

اقتراح قابل للاعتماد: RPO ≤24 ساعة مع نسخ يومي وقبل التحديثات، واحتفاظ 7 يومية/4 أسبوعية/6 شهرية حسب السعة، وRTO مستهدف ≤4 ساعات يُثبت بتمرين واقعي. هذه أهداف مقترحة لا ضمانات. إذا رفض العمل فقد يوم، تُختار وتُختبر استراتيجية أكثر تكرارًا أو base backup+WAL قبل الإطلاق؛ pg_dump لا يحقق PITR. [توثيق PostgreSQL 16](https://www.postgresql.org/docs/16/continuous-archiving.html).

**الاستعادة:** تنزيل نسخة من الوجهة الخارجية على مضيف استعادة مستقل، إلى حاوية اختبار disposable محلية عليه تطابق ضوابط الأداة (`APP_ENV=test` وcontainer ID/label وloopback)، مع scratch مشفر أو RAM. لا نضع رابط الإنتاج في verify ولا نضعف حواجزه. فحص البصمات والأعداد والمرفقات وAlembic ثم smoke tests مع تعطيل البريد؛ قياس الزمن. التحويل إلى تشغيل فعلي إجراء منفصل محكوم، لأن verify الحالي أداة تمرين وليست أمر استبدال إنتاج.

**الملفات:** `backend/alembic/env.py` و`versions/`، `backend/scripts/backup/iorp_backup.py`، `backend/scripts/recovery_drill.py`، `backend/tests/core/test_backup_tool.py`، `test_backup_roundtrip_isolated.py`، `test_recovery_drill.py`، `docs/operations/BACKUP_AND_RECOVERY.md`. إعداد timer/رفع خارجي لاحقًا ضمن ملفات النشر، دون إعادة كتابة أداة النسخ.

**القبول:** restore من النسخة الخارجية، نجاح migrations وسلامة ملفات الأعمال، استرداد مفاتيح MFA، إنذار عند فشل النسخ أو تجاوز عمرها، وعدم حذف آخر نسخة متحقق منها. **الخطر P0:** نسخة مشفرة بلا مفتاح، DB دون uploads، أو استعادة فوق الإنتاج. **الاعتماد:** 1–3؛ وجهة النسخ وRPO/RTO معتمدان قبل النقل الحقيقي.

## 5. نشر إنتاجي محكوم والتحديثات

**العمل:** ترقية نفس digests التي اجتازت staging؛ موافقة إصدار واحدة قبل الإنتاج وفق آلية المرحلة 2. مستخدم نشر مقيد بأوامر المشروع، SSH مع تحقق host key، وأسرار runtime خارج Git. صلاحية Docker تمنح سلطة واسعة على المضيف؛ لا منحها لحساب CI عام. لا auto-updater للصور ولا `latest` ولا `down -v` ولا prune شامل.

التسلسل: فحص المساحة والصحة → نسخة متسقة مؤكدة → نافذة صيانة إن لزم → migration منفردة → تشغيل الإصدار → readiness وsmoke → فتح المرور ومراقبة. أول انتقال من المحلي يحتاج نقل DB وuploads معًا، تجميد الكتابة بالمصدر، مطابقة البيانات، ومنع تشغيل مصدرين يقبلان الكتابة. لا نقل بيانات حقيقية ضمن staging دون إجراء خصوصية منفصل.

**التراجع:** احتفظ بالإصدار السابق وملف Compose وقيم الإعداد غير السرية ومعرف النسخة. الرجوع للصورة السابقة فقط عندما تكون متوافقة مع المخطط الجديد. عند عدم التوافق: إصلاح أمامي أو استعادة DB+uploads إلى موارد جديدة بعد قرار يقر بفقد كتابات ما بعد النسخة؛ لا استعادة صامتة ولا downgrade مدمر. لا يمكن ضمان zero downtime لكل migration.

**المراقبة:** فحص HTTPS خارجي؛ ready داخلي؛ تنبيه فشل الحاويات و5xx وزمن الاستجابة وCPU/RAM والقرص/inodes واتصالات DB وفشل PDF/SMTP وشهادة TLS وعمر آخر backup ونتيجة restore. تدوير السجلات وحجب tokens/passwords/OTP وروابط الاستعادة. البدء بأدوات VPS الموجودة إن كانت مناسبة؛ لا إلزام بمنصة مراقبة ثقيلة.

**الملفات:** workflows وCompose المقترحة في 2–3، وإعدادات `core/config.py` و`core/logging.py` وأدلة التشغيل الحالية. **القبول:** معاملات تجريبية مأذونة للعملاء والإنتاج والجودة والشحن والتقارير، فحص عزل منظمتين، rollback مجرّب في staging وتنبيهات تصل للمسؤول. **الخطر P0:** تشغيل قبل إثبات التعافي أو تحديث يؤثر على مشاريع أخرى. **الاعتماد:** نجاح 1–4، ثم تصريح نشر إنتاجي مستقل؛ هذه المهمة لا تمنحه.

## معلومات VPS المطلوبة قبل التنفيذ — تجمع مرة واحدة

1. نظام التشغيل وإصداره ومعمارية CPU، RAM/vCPU والمساحة الحرة/inodes وأحجام DB/uploads ومعدل نموها.
2. قائمة المشاريع والحاويات والعمليات الحالية؛ مالك 80/443 و3000/8080/5432، إصدارات Docker/Compose، هل Traefik موجود وإصداره وموقع إعداداته وشبكاته وآلية شهاداته؟ لا يلزم إرسال أسرار.
3. volumes ومسارات البيانات وملكيتها والنسخ الحالية، firewall وقواعد نشر Docker وSSH/VPN وصلاحيات المسؤول؛ حدود تعديل المكونات المشتركة.
4. نطاقا staging/production، مزود DNS ومن يديره، وجود CDN/proxy، اتصال SMTP Hostinger الصادر ومزود تنبيه التشغيل.
5. حساب/منظمة GitHub والـremote الحالي وخصوصيته وخطته وregistry، المسؤول عن مراجعة الإصدار ووسيلة نشر محدودة الصلاحية.
6. مصدر بيانات ريحانة الحالي وحجمها ومخطط Alembic، زمن الصيانة المقبول، RPO/RTO المقبولان، وجهة النسخ خارج الخادم ومدير المفاتيح ومسؤول تمرين الاستعادة.

## قائمة التنفيذ المرتبة

- [ ] جمع الجرد أعلاه دون تغيير VPS؛ توثيق حدوده داخل هذه الخطة.
- [ ] إغلاق تغييرات العمل وتثبيت commit الإصدار ونتائج اختباره.
- [ ] بناء صور production قابلة للتكرار واجتياز اختبارات الأمن والتقارير.
- [ ] تفعيل مستودع خاص وCI وصور immutable وبوابة نشر محددة.
- [ ] نشر staging معزول واختبار الشبكات والموارد وسير العمل.
- [ ] إثبات migrations والنسخ الخارجي والاستعادة ومفاتيح التعافي وrollback.
- [ ] اعتماد نافذة الإصدار ونقل البيانات، ثم نشر إنتاجي مصرح به ومراقب.

**غير منفذ عمدًا في هذه المهمة:** Dockerfiles وCI والنشر وتعديل إعدادات VPS ونقل البيانات وإعادة تشغيل الاختبارات. هذه خطة اكتشاف مبنية على الملفات الفعلية، وليست شهادة جاهزية أو إعلانًا بنجاح نشر.
