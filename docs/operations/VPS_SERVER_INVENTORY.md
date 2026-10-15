# جرد خادم VPS — المرجع الدائم قبل نشر IORP

تاريخ الجرد: 2026-10-15. الطريقة: أوامر قراءة فقط نفّذها مالك الخادم، ولم يُعدَّل أي شيء. يُحدَّث هذا الملف بعد كل تغيير على الخادم. لا يحتوي عنوان IP أو حسابات أو أسرار، فهذه تُحفظ خارج المستودع.

مرتبط بـ: [IORP_PRODUCTION_DEPLOYMENT_PLAN.md](../../IORP_PRODUCTION_DEPLOYMENT_PLAN.md) (المرحلة 3) و[BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md).

## 1. المواصفات

| البند | القيمة | ملاحظة |
|---|---|---|
| النظام | Ubuntu 24.04.3 LTS، x86_64، kernel 6.8 | متوافق مع صور CI (linux/amd64) |
| المعالج | 2 vCPU | محدود؛ محرك PDF هو الأثقل |
| الذاكرة | 7.8 GiB، المتاح وقت الجرد 6.3 GiB | الحاويات القائمة تستهلك ≈ 1.4 GiB |
| Swap | **لا يوجد** | مطلوب قبل النشر (§5) |
| القرص `/` | 96 GB، المستخدم 11 GB | صور Docker ≈ 8.3 GB |
| المنطقة الزمنية | UTC، الساعة متزامنة | توقيت المهام بـ UTC (الرياض = UTC+3) |
| Docker / Compose | 29.1.5 / v5.0.2 | |
| `daemon.json` | json-file بتدوير 10m×3؛ مجمّع عناوين `10.0.0.0/8` بحجم /24 | شبكات IORP الثابتة `172.28.x.0/24` لا تتعارض معه |
| حالة التحديث | 67 تحديثًا، وإعادة تشغيل مطلوبة | §5 |

## 2. ما يعمل على الخادم (لا يُلمس من IORP)

كل الحاويات `restart=unless-stopped` وبلا حدود ذاكرة. التنظيم: `/opt/apps/<اسم>` و`/opt/infrastructure/<اسم>`.

| الحاوية | المجلد | النطاق العام | الشبكات |
|---|---|---|---|
| traefik v3.1.7 | `/opt/infrastructure/traefik` | لوحة traefik (محمية بـ basicauth) | proxy |
| postgres:16-alpine + adminer | `/opt/infrastructure/postgres` | — (adminer على `127.0.0.1:8080` فقط) | internal_shared (+ adminer على proxy) |
| nexus-web | `/opt/apps/findocsmini/frontend` | nexus | proxy |
| installments-service | `/opt/apps/findocsmini/backend` | — | internal_shared |
| core-api | `/opt/apps/core-api` | core-api، و`nexus/api` | proxy, internal_shared |
| n8n | `/opt/apps/n8n` | n8n | proxy |
| uptime-kuma | `/opt/apps/uptime-kuma` | status | proxy |
| portainer | `/opt/apps/portainer` | portainer (**بلا تقييد وصول**) | proxy |

## 3. Traefik — كيف يدخل IORP

- مدخلا `web:80` (تحويل إلى HTTPS) و`websecure:443`.
- `exposedbydefault=false`، و`providers.docker.network=proxy`.
- الشهادات: resolver باسم `le`، بطريقة HTTP-01. لكل نطاق شهادة خاصة به، ولا حاجة إلى wildcard.
- مستوى السجل `DEBUG`، ويُخفَّض في مرحلة التأمين.

القيم في `deploy/env/<env>.env`:

| المتغير | staging | production |
|---|---|---|
| `IORP_PROJECT` | `iorp-staging` | `iorp-production` |
| `IORP_DOMAIN` | `iorp-staging.rehanh.cloud` | `iorp.rehanh.cloud` |
| `TRAEFIK_NETWORK` | `proxy` | `proxy` |
| `TRAEFIK_CERTRESOLVER` | `le` | `le` |
| `IORP_APP_SUBNET` | `172.28.10.0/24` | `172.28.11.0/24` |
| `IORP_TRUSTED_PROXY_IPS` (backend) | `172.28.10.0/24,10.0.1.0/24` | `172.28.11.0/24,10.0.1.0/24` |

`10.0.1.0/24` هي شبكة `proxy` وقت الجرد. يُعاد التحقق منها قبل كل نشر بالأمر `docker network inspect proxy --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}'`، لأن إعادة إنشاء الشبكة قد تغيّرها.

**مقايضة معتمدة:** الواجهة تنضم إلى `proxy` المشتركة بدل شبكة دخول خاصة، لأن الشبكة الخاصة تتطلب تعديل Traefik. الواجهة إذن تصل شبكيًا إلى portainer وadminer وn8n، وكل منها محمي بتسجيل دخول. أما الخادم وقاعدة البيانات ومحرك PDF فلا ينضم أي منها إلى `proxy`.

## 4. ميزانية الموارد

حدود `deploy/compose.yaml` لكل بيئة: frontend 512M، backend 1G، postgres 1G، renderer 1G، gateway 64M، أي ≈ 3.6 GiB.

```
القائم (nexus وغيره) ≈ 1.4 GiB + IORP إنتاج ≈ 3.6 GiB + النظام والذاكرة المؤقتة ≈ 1.5 GiB ≈ 6.5 من 7.8 GiB
```

- **staging عند الحاجة فقط:** يُشغَّل للاختبار، ثم يُوقف بـ `docker compose ... stop`. لا يُستخدم `down`، كي تبقى صوره (§6).
- قاعدة IORP مستقلة: Postgres 16 بصورة مثبتة بالـ digest. لا يستخدم IORP قاعدة `internal_shared` أبدًا.

## 5. تعديلات التجهيز المعتمدة (لم تُنفَّذ بعد)

تُنفَّذ بالترتيب، بقائمة أوامر يراجعها المالك قبل التنفيذ:

1. **swap بحجم 4 GiB**، مع `vm.swappiness=10`.
2. **إعادة تشغيل للتحديثات** في وقت هادئ (فجرًا بتوقيت الرياض)، ثم التحقق أن الحاويات التسع عادت، وأن nexus يستجيب.
3. **SSH بالمفاتيح فقط:**
   - الوضع الحالي: `PasswordAuthentication yes` فعّال، لأن السطر `yes` في `/etc/ssh/sshd_config` يسبق `no` في الملف نفسه، والقيمة الأولى هي المطبّقة.
   - المفتاح الوحيد المسجل هو غالبًا مفتاح النشر `github-actions-core-api`. **لا يُحذف**، وإلا توقف نشر core-api.
   - مفتاح المالك الشخصي غير مسجل؛ اختبار الدخول به رُفض في 2026-10-15.
   - الترتيب: إضافة مفتاح المالك إلى الموجود دون استبداله، ثم اختباره من جلسة جديدة مع إبقاء جلسة مفتوحة، ثم تعطيل كلمة المرور، ثم `sshd -t` و`reload`، ثم اختبار جلسة جديدة. يبقى الدخول عبر لوحة المزوّد (console) طريق الطوارئ.
   - يبقى `sudo` بكلمة مرور.
4. **دخول الخادم إلى ghcr.io** بمفتاح قراءة فقط (`read:packages`).

## 6. مهام التنظيف الموجودة وأثرها على IORP

`/etc/cron.d/docker-image-prune` يعمل يوميًا الساعة 00:16 UTC، بالأمر `docker image prune -af --filter "until=24h"`. يحذف كل صورة لا تستخدمها حاوية (ولو متوقفة) وعمرها أكثر من 24 ساعة. ويوجد `docker-builder-prune` أسبوعيًا.

**القرار:** لا تُعدَّل هذه المهام. صورة الإصدار السابق لا تُحفظ على الخادم، والرجوع إليها يكون بسحبها من ghcr.io بالوسم أو بالـ digest. ولا حاجة إلى مهمة تنظيف صور خاصة بـ IORP.

## 7. الأمان — الحالة

| البند | الحالة |
|---|---|
| ufw | ✅ deny incoming؛ مفتوح فقط 22 و80 و443 |
| منافذ Docker المنشورة | ✅ 80 و443 لـ traefik فقط، وadminer على loopback |
| root عبر SSH | ✅ معطّل |
| fail2ban | ✅ jail واحد: sshd |
| unattended-upgrades | ✅ يعمل |
| الدخول بكلمة المرور عبر SSH | ⚠️ مفعّل (§5.3) |
| portainer | 🔴 مكشوف للإنترنت، وحمايته شاشة دخوله فقط، وهو يملك صلاحيات Docker. يُقيَّد قبل نقل بيانات الإنتاج |
| سجل traefik DEBUG | 🟡 يُخفَّض إلى INFO |
| وسم `latest` لـ n8n وadminer | 🟡 يتغير الإصدار دون قصد؛ خارج نطاق IORP |

## 8. التشغيل الدائم ونوافذ الصيانة

المستخدمون يعملون في أي وقت (24/7). لذلك تُجدول كل عملية قد توقف النظام (نشر إصدار، migration، إعادة تشغيل) بين **02:00 و05:00 بتوقيت الرياض** (23:00–02:00 UTC)، مع إشعار مسبق للمستخدمين. ويكون النسخ الاحتياطي اليومي في هذه النافذة، بعيدًا عن موعد مهمة التنظيف 00:16 UTC.

## 9. النسخ الاحتياطي خارج الخادم (معتمد)

- الوجهة: Google Drive للمالك عبر `rclone`، بصلاحية `drive.file`. يرى الخادم ما أنشأه فقط، في مجلد `iorp-backups` يُنشئه rclone.
- كل نسخة **مشفرة على الخادم قبل الرفع** بأداة `iorp_backup.py`. مفتاح فك التشفير يحفظه المالك خارج الخادم؛ ضياعه يجعل كل النسخ بلا قيمة.
- الاحتفاظ: 7 يومية، و4 أسبوعية، و6 شهرية. النسخة تشمل قاعدة البيانات والمرفقات معًا.
