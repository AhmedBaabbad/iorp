# صور الإنتاج على GHCR

ينشر job `images` الصور الأربع بعد البناء والفحوص في job نفسه، فقط عند `push` إلى `main`:
`ghcr.io/ahmedbaabbad/iorp/{backend,frontend,report-gateway,report-renderer}:<SHA كامل>`.
لا يوجد وسم `latest`، ولا يعاد البناء عند النشر. يسجل ملخص CI مرجع كل صورة مع digest وimage ID.
وسم OCI `org.opencontainers.image.source` يربط الصور بمستودع `AhmedBaabbad/iorp`.
تكون الحزم الجديدة خاصة افتراضيًا؛ لا يغيّر workflow إعداد الرؤية لحزمة موجودة. تحقق بعد أول نشر من أن الحزم الأربع **Private** ومن ربطها بالمستودع ومن صلاحية Actions عليها.

## سحب الصور على الخادم

أنشئ PAT classic للمالك بصلاحية `read:packages` فقط، مع صلاحية الوصول إلى الحزم الخاصة.
استخدم حساب نظام النشر نفسه في تسجيل الدخول والسحب. أدخل المفتاح تفاعليًا؛ لا تكتبه في ملف المستودع أو في سجل الأوامر:

```bash
read -rsp 'GHCR read-only token: ' GHCR_READ_TOKEN; echo
printf '%s' "$GHCR_READ_TOKEN" | docker login ghcr.io -u AhmedBaabbad --password-stdin
unset GHCR_READ_TOKEN
```

تُحفظ بيانات الدخول في إعداد Docker لذلك الحساب؛ احمِ هذا الملف أو استخدم credential helper.
في ملف البيئة الخاص بالخادم، اضبط:

```dotenv
IORP_REGISTRY=ghcr.io/ahmedbaabbad/iorp
IORP_IMAGE_TAG=<SHA كامل من تشغيل CI ناجح على main>
```

ثم اسحب الصور الأربع دون بناء محلي (استبدل `staging` بـ `production` عند النشر المعتمد):

```bash
docker compose --env-file deploy/env/staging.env -f deploy/compose.yaml pull frontend backend report-gateway report-renderer
```

قارن digests الناتجة بملخص CI. النشر إجراء مستقل في نافذة الصيانة وبعد النسخ الاحتياطي وفحص الترحيلات:

```bash
docker compose --env-file deploy/env/staging.env -f deploy/compose.yaml up -d --no-build
```

## الرجوع إلى إصدار سابق

احتفظ خارج المستودع بالـ SHA الحالي والسابق وdigests الصور. غيّر `IORP_IMAGE_TAG` إلى SHA سابق نجح في CI وما زال محفوظًا في GHCR، ثم نفّذ أمرَي `pull` و`up -d --no-build` أعلاه للبيئة المقصودة، وافحص الصحة وتسجيل الدخول والتقارير.
الرجوع إلى الصور لا يعيد قاعدة البيانات: راجع توافق migrations قبل الرجوع؛ استخدم خطة الاستعادة المعتمدة عند وجود تغيير غير متوافق. راجع [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md).

## الاحتفاظ والمراجعة

يعمل `ghcr-retention.yml` أسبوعيًا يوم الاثنين 02:30 بتوقيت الرياض (الأحد 23:30 UTC).
يحمي أحدث 10 إصدارات **لكل صورة** حسب تاريخ الإنشاء، ويعرض الإصدارات الأقدم ومعرّفاتها ووسومها وdigests في ملخص التشغيل. التشغيل المجدول لا يحذف شيئًا، بما في ذلك الإصدارات غير الموسومة.

راجع المرشحين مقابل SHAs المنشورة على staging وproduction وإصدارات الرجوع المطلوبة. بعد اعتماد القائمة، شغّل workflow يدويًا من `main` واختر صورة واحدة وأدخل معرّفات الإصدارات المعتمدة، مفصولة بفواصل دون مسافات، في `reviewed_version_ids`. تعاد قراءة القائمة عند التنفيذ، ويُرفض أي معرّف مفقود أو ضمن أحدث 10، ثم تحذف action المثبتة تلك المعرّفات فقط. كرر للصورة التالية عند الحاجة.
قد يبقى أكثر من 10 إصدارات حتى تكتمل المراجعة، أو لحماية إصدار مستخدم؛ لا توجد إزالة تلقائية للوسوم. صلاحية workflow هي `packages: write` فقط دون checkout أو صلاحية محتويات المستودع.

المراجع الرسمية: [GHCR والمصادقة والرؤية وربط المستودع](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)، [مدخلات إجراء حذف الإصدارات المثبت](https://github.com/actions/delete-package-versions/blob/e5bc658cc4c965c472efe991f8beea3981499c55/action.yml).
