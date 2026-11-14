# تشغيل النسخ الاحتياطي للإنتاج

قرار المالك **2026-11-14**: **لا نسخ احتياطي لـstaging**. الجدولة والتمارين والمراقبة هنا للإنتاج فقط؛ المنسّق يرفض غير `production` قبل قراءة الأسرار أو إنشاء الموارد. هذه تعليمات للمالك بعد اعتماد الإصدار، وليست إجراءً نُفّذ على السيرفر أثناء إعداد المستودع.

أهداف التعافي: **RPO = 24 ساعة، RTO = ساعتان**. الجولة اليومية 23:30 UTC؛ فحص القرص كل 15 دقيقة. يُقاس RTO قبل الإطلاق ثم شهريًا على حجم مماثل للإنتاج؛ CI الاصطناعي ليس قياس أداء الإنتاج.

## الضمانات والاحتفاظ

- التنسيق على المضيف تحت `flock` واحد، بلا docker.sock داخل التطبيق. يلزم نشر إنتاج قائم مع جامع `backup` معتمد وPostgreSQL 16. هذا الإصلاح لا يغيّر Compose أو صور التطبيق ولا يرقّي التطبيق.
- الترتيب: snapshot القاعدة ثم المرفقات ثم رفع المشفّر وتنزيل النسخة الجديدة من Drive واسترجاعها في PostgreSQL مؤقت وكتابة receipt ثم retention ثم Push. ليست لقطة ذرية ولا PITR؛ لا تجميد كتابة في v1. `referenced_but_missing` يستلزم إعادة جمع واحدة ثم فشل إن استمر. إضافة استبدال ملف in-place لمفتاح قائم تستلزم مراجعة الاتساق.
- مفتاح إنتاج جديد مستقل في ملف `600`، خارج Git وCI. الملفات البعيدة الخمسة مشفّرة، بما فيها manifest وreceipt وcompletion. يسجل `complete.enc` بصمتَي SHA-256 وMD5. لا رفع لبيانات وصفية واضحة.
- لا حذف ولا عزل محلي قبل اكتمال التحقق من **الكتالوج البعيد كله**. تنزيل القديم يقتصر على `complete.enc` و`manifest.json.enc` و`verification.json.enc`؛ مقارنة الحمولة بـMD5 الأصلي دون `--download`، لا تنزيل الحمولات القديمة يوميًا.
- البعيد: اتحاد 7 أيام و4 أسابيع ISO و6 أشهر مع حماية أحدث نسخة متحقق منها. المجلد المؤرّخ بلا `complete.enc` رفع منقطع يُترك ولا يُعتمد ولا يُحذف. مجلد بعيد مجهول أو تاريخ غير صالح أو عناصر زائدة داخل نسخة مكتملة يمنع الاحتفاظ بـ`remote-layout`. الملفات المنفردة بجذر البيئة لا تدخل `lsf --dirs-only` وتُترك. لا purge أو sync لجذر البيئة.
- المحلي: أحدث **3 نسخ سليمة ضمن keep البعيد**، والنسخة الجديدة ضمنها دائمًا. بعد نجاح purge البعيد لكل اسم خارج keep يُحذف مجلده المحلي السليم في التشغيل نفسه؛ إن فشل purge يبقى المحلي ويظهر `remote-prune`. النسخة اليدوية قبل migration ثم الليلية حالة طبيعية: لا عزل ولا تحذير.
- العزل مخصص لمعطوب أو symlink أو اسم غير صالح أو عنصر غريب أو يتيم غير مفسر بقرار الجولة (مثل بقايا الكود القديم أو انقطاع بين الحذف البعيد والمحلي). يُنقل دون حذف إلى `backups/quarantine/<random-id>/<original-name>`، ثم يستمر احتفاظ السليم. symlink يُنقل بذاته دون لمس هدفه. تظهر `warning reason=local-quarantined` ورسالة Push `backup complete: local-quarantined` فقط عند عزل عنصر جديد. النقل على القرص نفسه لا يحرر مساحة؛ يراجع المالك العزل يدويًا، ولا تنظيف آلي له. المكان الصحيح للتمارين هو `backups/manual-receipts` خارج `local`.
- فساد أي نسخة بعيدة مكتملة يمنع كل الحذف، ولو نجحت النسخة الجديدة. العلامات القديمة غير المتوافقة تُحقق يدويًا ولا تُتجاوز. فشل عزل عنصر يمنع بقية الحذف برمز واضح.
- scratch خاص `700` ويُمسح مع موارد PostgreSQL المؤقتة في النجاح والفشل. تبقى حراسات `APP_ENV=test` و`IORP_RESTORE_CONTAINER_ID` وlabel `iorp.purpose=backup-test` وloopback و`IORP_RESTORE_SCRATCH`، بلا bind mounts لقاعدة الإنتاج. انقطاع الكهرباء/SIGKILL يحتاج فحص البقايا يدويًا، لا global prune. لا اشتراط swap مشفر في v1 لأن القاعدة الحية أصلًا غير مشفرة على القرص نفسه.
- حدود الذاكرة وCPU وI/O والمهلة والحجم القائمة باقية؛ راقب مساحة quarantine أيضًا. v1 تستخدم حساب التطبيق من ملف `DATABASE_URL` منفصل؛ القارئ المخصص دين تقني إلى حين اختبار GRANT/default privileges. لا تعديل لموارد التطبيقات الأخرى.
- الفشل: `iorp-backup: failed stage=<stage> reason=<code>`. يقبل السبب فقط `^[a-z][a-z0-9-]{0,40}$` وإلا `unexpected`. لا نص استثناء أو traceback أو مسار أو URL أو stderr لـrclone في خرج المنسّق. لا `set -x` أو طباعة env أو Docker inspect كامل، ولا نشر journal الخام الذي قد يحمل بيانات مضيف من systemd.

## التثبيت وتفعيل الإنتاج — نفّذ بالترتيب

كل القيم الحقيقية من مخزون المالك الخاص وتُكتب على المضيف فقط. `BASE` جذر نشر الإنتاج؛ ملف Compose env هو `env/project.env` تحته. أمثلة `/REPLACE` ليست إعدادًا جاهزًا. توقف عند أي فشل. لا تُفعّل timers قبل نجاح التحقق offline.

1. في جلسة إدارية، أوقف staging دون حذف بياناتها أو مفاتيحها. masking يمنع إعادة تشغيل المثيلات القديمة عرضًا.

   ```bash
   set -euo pipefail
   umask 077
   if systemctl cat iorp-backup@.service >/dev/null 2>&1; then
     sudo systemctl disable --now iorp-backup@staging.timer iorp-backup-disk@staging.timer
     sudo systemctl stop iorp-backup@staging.service iorp-backup-disk@staging.service
   fi
   sudo systemctl mask iorp-backup@staging.timer iorp-backup-disk@staging.timer \
     iorp-backup@staging.service iorp-backup-disk@staging.service
   ```

2. أدخل جذر الإنتاج ومالك النشر ومستودع المصدر العام بلا بيانات اعتماد. SHA لكود المضيف المراجع؛ صورة الجامع وCompose يظلان للنشر الحالي المعتمد، ولا تُشغّل migration هنا.

   ```bash
   read -rp 'Private production root, ending /production: ' BASE
   [[ "$BASE" =~ ^/[A-Za-z0-9_./-]+/production$ ]]
   [[ "$BASE" = "$(realpath -m -- "$BASE")" ]]
   read -rp 'Deployment owner username: ' OWNER
   id "$OWNER" >/dev/null
   read -rp 'Public source repository URL, without credentials: ' SOURCE_REPOSITORY
   read -rp 'Reviewed host-code commit SHA (40 hex): ' SOURCE_SHA
   [[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]
   sudo apt-get update
   sudo apt-get install -y python3-venv rclone git
   sudo install -d -m 700 "$BASE/backups" "$BASE/backup-runtime" "$BASE/env/rclone" "$BASE/env/docker"
   sudo git clone "$SOURCE_REPOSITORY" "$BASE/backup-runtime/source"
   SOURCE=$BASE/backup-runtime/source
   sudo git -C "$SOURCE" checkout --detach "$SOURCE_SHA"
   sudo python3 -m venv "$BASE/backup-runtime/venv"
   PY=$BASE/backup-runtime/venv/bin/python
   OPS=$SOURCE/backend/scripts/backup/ops_backup.py
   sudo "$PY" -m pip install --require-hashes --no-deps -r "$SOURCE/backend/requirements.lock"
   ```

3. جهّز الملفات الخاصة وافتحها بالمحرر دون عرض محتواها. `backup-database.env` نسخة مستقلة من `DATABASE_URL` فقط. اضبط **ثلاثة** Push monitors للإنتاج: daily وrestore بمهلة 26 ساعة، وdisk بمهلة 20 دقيقة وتنبيه عند تجاوز 80%؛ اختبر قنوات التنبيه. اعتماد سحب الصور منفصل لخدمة النسخ في `env/docker`، لا home مستخدم معلوم، ولا token في argv.

   ```bash
   sudo install -m 600 "$SOURCE/deploy/env/backup-database.env.example" "$BASE/env/backup-database.env"
   sudo install -m 600 "$SOURCE/deploy/env/backup-push.env.example" "$BASE/env/backup-push.env"
   sudoedit "$BASE/env/backup-database.env" "$BASE/env/backup-push.env"
   read -rp 'Container registry from private inventory: ' REGISTRY
   sudo env DOCKER_CONFIG="$BASE/env/docker" docker login "$REGISTRY"
   ```

4. أنشئ remote مستقلًا للإنتاج بـ**drive.file** فقط. أجب No للمتصفح على المضيف. على **جهاز المالك** شغّل أمر `rclone authorize` الذي تعرضه جلسة الإعداد بنفس OAuth client وscope blob، وأكمل المتصفح هناك، ثم أعد الناتج إلى prompt الخاص فقط، لا Git أو سجل أو محادثة. استخدم client يملكه المالك ويسمح بتفويض طويل العمر؛ لا توسّع scope لحل خطأ وصول.

   ```bash
   sudo rclone config --config "$BASE/env/rclone/rclone.conf"
   sudo chmod 600 "$BASE/env/rclone/rclone.conf"
   read -rp 'Private production rclone remote name: ' REMOTE
   [[ "$REMOTE" =~ ^[A-Za-z0-9_-]+$ ]]
   sudo rclone --config "$BASE/env/rclone/rclone.conf" mkdir "$REMOTE:iorp-backups/production"
   ```

5. ولّد مفتاح إنتاج **جديدًا** بكتابة حصرية. لا تستخدم مفتاح staging ولا تستبدل مفتاحًا موجودًا؛ النسخ القديمة تحتاجه طوال الاحتفاظ. حزمة التعافي تشمل `IORP_BACKUP_KEY` و`SECRET_KEY` و`PLATFORM_MFA_KEYS` للإنتاج، دون عرضها.

   ```bash
   sudo "$PY" - "$BASE" "$SOURCE" "$OWNER" <<'PY'
   import os, sys, pwd
   from pathlib import Path
   from cryptography.fernet import Fernet
   sys.path.insert(0, sys.argv[2] + '/backend/scripts/backup')
   from ops_backup import read_env
   base = Path(sys.argv[1]); os.umask(0o077)
   app = read_env(base / 'env/backend.env')
   if any(not app.get(k) for k in ('SECRET_KEY', 'PLATFORM_MFA_KEYS')):
       raise SystemExit('Recovery material unavailable')
   recovery = {'IORP_BACKUP_KEY': Fernet.generate_key().decode(),
               'SECRET_KEY': app['SECRET_KEY'], 'PLATFORM_MFA_KEYS': app['PLATFORM_MFA_KEYS']}
   with (base / 'env/backup-key.env').open('x') as stream:
       stream.write('IORP_BACKUP_KEY=' + recovery['IORP_BACKUP_KEY'] + '\n')
   bundle = base / 'env/recovery.env'
   with bundle.open('x') as stream:
       stream.write(''.join(k + '=' + v + '\n' for k, v in recovery.items()))
   owner = pwd.getpwnam(sys.argv[3]); os.chown(bundle, owner.pw_uid, owner.pw_gid)
   PY
   sudo chmod 600 "$BASE/env/backup-key.env" "$BASE/env/recovery.env"
   ```

6. على **جهاز المالك** انقل حزمة التعافي إلى مخزن offline مشفر مستقل عن المضيف وDrive. أغلق المخزن وافتحه واستخرج نسخته المحفوظة فعليًا ثم أعدها باسم مختلف؛ cache وDownloads ليسا دليل حفظ. أدخل بيانات SSH من المخزون الخاص، لا في المستودع.

   ```bash
   umask 077
   read -rp 'SSH destination from private inventory: ' SSH_DESTINATION
   read -rp 'Same private production root: ' BASE
   scp "$SSH_DESTINATION:$BASE/env/recovery.env" ./production-recovery.env
   # احفظه في offline وأغلق المخزن وافتحه، ثم استخرج إلى offline-recovered.env.
   scp ./offline-recovered.env "$SSH_DESTINATION:$BASE/env/offline-recovered.env"
   ```

7. بعد اعتماد المالك تفعيل الإنتاج، أنشئ `backup-ops.env` الخاص. المطلوب صراحةً: `ENVIRONMENT=production` و`ENABLED=yes` و`PRODUCTION_APPROVED=yes` و`STATE_DIR` للإنتاج. لا تنسخ env التطبيق كله ولا أسرارًا إلى source.

   ```bash
   sudo "$PY" - "$BASE" "$SOURCE" "$REMOTE" <<'PY'
   import os, sys
   from pathlib import Path
   sys.path.insert(0, sys.argv[2] + '/backend/scripts/backup')
   from ops_backup import read_env
   base = Path(sys.argv[1]); os.umask(0o077)
   values = read_env(Path(sys.argv[2]) / 'deploy/env/backup-ops.env.example')
   values.update(ENVIRONMENT='production', ENABLED='yes', PRODUCTION_APPROVED='yes',
       STATE_DIR=str(base / 'backups'), COMPOSE_FILE=str(base / 'compose.yaml'),
       COMPOSE_ENV_FILE=str(base / 'env/project.env'),
       DATABASE_ENV_FILE=str(base / 'env/backup-database.env'), KEY_ENV_FILE=str(base / 'env/backup-key.env'),
       PUSH_ENV_FILE=str(base / 'env/backup-push.env'), RCLONE_CONFIG=str(base / 'env/rclone/rclone.conf'),
       RCLONE_REMOTE=sys.argv[3])
   with (base / 'env/backup-ops.env').open('x') as stream:
       stream.write(''.join(k + '=' + v + '\n' for k, v in values.items()))
   PY
   ```

8. نفّذ نسخة يدوية ثم أثبت أن **المفتاح المستخرج من offline** يفك النسخة الموجودة أصلًا في Drive؛ نجاح الجمع بمفتاح أصلي وحده لا يثبت الحفظ. عدم تطابق مواد التعافي يوقف التفعيل دون طباعة أسماء أو قيم الأسرار.

   ```bash
   sudo env DOCKER_CONFIG="$BASE/env/docker" "$PY" "$OPS" daily --config "$BASE/env/backup-ops.env"
   sudo "$PY" - "$BASE" "$SOURCE" <<'PY'
   import os, sys
   from pathlib import Path
   sys.path.insert(0, sys.argv[2] + '/backend/scripts/backup')
   from ops_backup import read_env
   base = Path(sys.argv[1]); os.umask(0o077)
   saved = read_env(base / 'env/offline-recovered.env')
   app = read_env(base / 'env/backend.env')
   expected = {'IORP_BACKUP_KEY': read_env(base / 'env/backup-key.env')['IORP_BACKUP_KEY'],
               'SECRET_KEY': app['SECRET_KEY'], 'PLATFORM_MFA_KEYS': app['PLATFORM_MFA_KEYS']}
   if saved != expected:
       raise SystemExit('Offline recovery check failed')
   with (base / 'env/offline-key.env').open('x') as stream:
       stream.write('IORP_BACKUP_KEY=' + saved['IORP_BACKUP_KEY'] + '\n')
   values = read_env(base / 'env/backup-ops.env')
   values['KEY_ENV_FILE'] = str(base / 'env/offline-key.env')
   with (base / 'env/offline-probe.env').open('x') as stream:
       stream.write(''.join(k + '=' + v + '\n' for k, v in values.items()))
   PY
   sudo env DOCKER_CONFIG="$BASE/env/docker" "$PY" "$OPS" drill --config "$BASE/env/offline-probe.env"
   ```

9. ثبّت وحدات النسخ بعد ضبط مساراتها إلى جذر النشر المُدخل، ثم فعّل **production فقط**. راقب أول تشغيل timer فعلي 23:30 UTC. لا تغيّر وحدات التطبيقات الأخرى أو Compose أو صورها.

   ```bash
   sudo "$PY" - "$SOURCE" "$BASE" <<'PY'
   import sys
   from pathlib import Path
   source, base = Path(sys.argv[1]), Path(sys.argv[2])
   for name in ('iorp-backup@.service', 'iorp-backup@.timer', 'iorp-backup-disk@.service', 'iorp-backup-disk@.timer'):
       text = (source / 'deploy/backup' / name).read_text()
       text = text.replace('/opt/apps/iorp/%i', str(base.parent) + '/%i')
       target = Path('/etc/systemd/system') / name
       target.write_text(text); target.chmod(0o644)
   PY
   sudo systemctl daemon-reload
   sudo systemctl enable --now iorp-backup@production.timer iorp-backup-disk@production.timer
   systemctl list-timers 'iorp-backup*'
   sudo systemctl show iorp-backup@production.service -p Result -p ExecMainStatus
   ```

10. بعد نجاح التحقق احذف **نسخ النقل والتحقق المؤقتة فقط**؛ هذه خطوة تعامل مع الأسرار، وليست تراجعًا. أبقِ `backup-key.env` التشغيلي وحزمة offline. على جهاز المالك تخلّص من نسختَي النقل الواضحتين بإجراء الأسرار المعتمد، بعد التأكد من حفظ المخزن المشفر. لا تنفّذ هذه الخطوة إذا فشل التحقق.

    ```bash
    sudo rm -- "$BASE/env/recovery.env" "$BASE/env/offline-recovered.env" \
      "$BASE/env/offline-key.env" "$BASE/env/offline-probe.env"
    ```

## نسخة قبل كل migration في الإنتاج

استخدم متغيرات التثبيت الخاصة في جلسة الصيانة. إن كانت جولة أخرى تعمل، انتظر نهايتها ثم اطلب جولة جديدة. لا تتجاوز فشل retention أو Push لمجرد وجود dump.

1. شغّل الخدمة وانتظر نجاحها وخروج المنسّق بصفر، قبل `migrate`.

   ```bash
   sudo systemctl start iorp-backup@production.service
   test "$(systemctl show iorp-backup@production.service -p Result --value)" = success
   test "$(systemctl show iorp-backup@production.service -p ExecMainStatus --value)" = 0
   ```

2. تحقق من receipt أحدث نسخة محلية سليمة ومن وصول daily/restore Push. الجولة تكون قد نزّلت النسخة من Drive واستعادتها؛ لا تعرض manifest أو أسماء الملفات.

   ```bash
   sudo "$PY" - "$BASE" "$SOURCE" <<'PY'
   import sys
   from pathlib import Path
   sys.path.insert(0, sys.argv[2] + '/backend/scripts/backup')
   from ops_backup import backup_name, matching_receipt
   local = Path(sys.argv[1]) / 'backups/local'
   folders = [p for p in local.iterdir() if p.is_dir() and not p.is_symlink() and backup_name(p.name)]
   if not folders or not matching_receipt(max(folders, key=lambda p: p.name)):
       raise SystemExit('Verified receipt unavailable')
   print('verified receipt ok=true')
   PY
   ```

3. بعد نجاح الفحوص فقط نفّذ migration بإجراء النشر المعتمد. احفظ إصدار وأسرار ما قبل الترحيل في المخزن الخاص. لا migration تلقائيًا ضمن النسخ الاحتياطي.

## فحص دوري لحجم العزل

بعد ضبط `BASE` من إعداد التثبيت الخاص، اعرض الحجم بأمر قراءة فقط إن كان المجلد موجودًا. نموه يستلزم مراجعة المالك؛ لا يُنشأ العزل في التشغيل الطبيعي ولا يُنظّف تلقائيًا.

```bash
if sudo test -d "$BASE/backups/quarantine"; then
  sudo du -sh -- "$BASE/backups/quarantine"
fi
```

## تجربة الاسترجاع: قبل الإطلاق ثم شهريًا

إضافةً للتحقق اليومي، ينفّذ المالك `drill` مستقلًا **قبل الإطلاق ثم مرة كل شهر**، بمفتاح مستخرج حديثًا من offline، ومن Drive لا القرص المحلي. استخرج الحزمة وأعد `offline-recovered.env` الخاص كما في الخطوة 6. أعد تنفيذ **مقطع Python فقط** من الخطوة 8 لتحضير `offline-key.env` و`offline-probe.env` ومقارنتهما بالإعداد التشغيلي؛ لا تكرر أمر `daily`. لا يجمع `drill` نسخة جديدة ولا يطبّق retention أو يكتب على قاعدة الإنتاج.

1. قِس الزمن من بداية التنزيل لنهاية التحقق، وراجع معه وقت تجهيز موارد التعافي والتحويل وفحوص التطبيق ضمن هدف الساعتين.

   ```bash
   START=$(date -u +%s)
   sudo env DOCKER_CONFIG="$BASE/env/docker" "$PY" "$OPS" drill --config "$BASE/env/offline-probe.env"
   ELAPSED=$(( $(date -u +%s) - START ))
   test "$ELAPSED" -le 7200
   ```

2. النجاح يعني exit صفر و`iorp-backup: success`، وreceipt **جديد** في `backups/manual-receipts` يحوي `ok=true` وبصمة manifest المطابقة. `verify` يفحص الأعداد وAlembic والمرفقات. افحص RESTORE Push واختفاء scratch والحاوية والvolume والشبكة الخاصة بالجولة. احفظ الوقت والنتيجة في سجل المالك الخاص، لا receipt أو عناوين أو أسرار في PR.

   ```bash
   sudo "$PY" - "$BASE" <<'PY'
   import json, sys
   from pathlib import Path
   root = Path(sys.argv[1]) / 'backups'
   receipts = list((root / 'manual-receipts').glob('*.json'))
   if not receipts or json.loads(max(receipts, key=lambda p: p.stat().st_mtime_ns).read_text()).get('ok') is not True:
       raise SystemExit('Restore receipt unavailable')
   if (root / 'scratch').exists():
       raise SystemExit('Restore cleanup incomplete')
   print('drill receipt ok=true; scratch absent')
   PY
   ```

3. بعد نجاح التمرين وحفظ دليله الخاص، أزل نسخ التحقق المؤقتة لتكون الجولة الشهرية التالية مستندة إلى استخراج جديد من offline.

   ```bash
   sudo rm -- "$BASE/env/offline-recovered.env" "$BASE/env/offline-key.env" "$BASE/env/offline-probe.env"
   ```

إذا تجاوز الزمن ساعتين أو فشل التحقق أو بقيت موارد التمرين فلا تعتمد جاهزية الإطلاق؛ حقق وأعد القياس. انقطاع daily أكثر من 26 ساعة يعني أن هدف RPO لم يعد متحققًا: عالج تنبيه Kuma فورًا. quarantine يستلزم مراجعة مساحة، ولا يبرر حذفًا آليًا.

## الاسترجاع الفعلي — إجراء طوارئ منفصل ومتعمد

ليس `drill` ولا timer. يوافق المالك على نقطة التعافي وفقد الكتابات اللاحقة، ويوقف الكتابات والمهام بإجراء الصيانة. يلزم مصدر الإصدار وأسرار الإنتاج من offline وخادم PostgreSQL 16 وvolume uploads **جديدان**، لا الموارد الحالية. لا DROP ولا `--clean` على الإنتاج الحالي.

1. نفّذ التمرين السابق أولًا. تُنفّذ بقية خطوات الطوارئ من **جلسة root واحدة** حتى تتطابق ملكية الملفات وأدوات PostgreSQL. أعد استخراج حزمة offline إلى `env/offline-recovered.env` الخاص كما في الخطوة 6، ثم أدخل المسارات وremote من السجل الخاص. عند فقد المضيف يلزم تجهيز runtime وrclone من مخزون التعافي؛ لا تولّد مفتاحًا جديدًا بدل المحفوظ. نزّل الملفات المشفّرة الخمسة فقط.

   ```bash
   sudo -i
   set -euo pipefail
   umask 077
   read -rp 'Private production deployment root: ' BASE
   [[ "$BASE" =~ ^/[A-Za-z0-9_./-]+/production$ ]]
   SOURCE=$BASE/backup-runtime/source
   PY=$BASE/backup-runtime/venv/bin/python
   read -rp 'Private production rclone remote name: ' REMOTE
   [[ "$REMOTE" =~ ^[A-Za-z0-9_-]+$ ]]
   read -rp 'Owner-approved completed backup ID: ' BACKUP_ID
   [[ "$BACKUP_ID" =~ ^iorp-[0-9]{8}T[0-9]{6}Z$ ]]
   read -rp 'New absolute recovery workspace: ' RECOVERY
   [[ "$RECOVERY" =~ ^/[A-Za-z0-9_./-]+$ && "$RECOVERY" != / ]]
   sudo mkdir -m 700 "$RECOVERY"
   sudo mkdir -m 700 "$RECOVERY/sealed"
   for name in database.dump.enc uploads.tar.gz.enc manifest.json.enc verification.json.enc complete.enc; do
     sudo rclone --config "$BASE/env/rclone/rclone.conf" copyto \
       "$REMOTE:iorp-backups/production/$BACKUP_ID/$name" "$RECOVERY/sealed/$name"
   done
   ```

2. بمفتاح الإنتاج المستعاد من offline افحص completion والبصمتين والmanifest والreceipt، ثم فك الحمولات إلى مساحة التعافي الخاصة. لا تطبع البيانات الوصفية.

   ```bash
   sudo "$PY" - "$BASE" "$SOURCE" "$RECOVERY" <<'PY'
   import json, sys
   from pathlib import Path
   sys.path.insert(0, sys.argv[2] + '/backend/scripts/backup')
   import iorp_backup as tool
   from ops_backup import read_env, checksums, check_manifest, matching_receipt, PAYLOADS
   base, root = Path(sys.argv[1]), Path(sys.argv[3]); folder = root / 'sealed'
   key = read_env(base / 'env/offline-recovered.env')['IORP_BACKUP_KEY']
   tool.decrypt_file(folder / 'complete.enc', folder / 'complete.json', key)
   expected = json.loads((folder / 'complete.json').read_text())
   if set(expected) != {*PAYLOADS, 'verification.json.enc'} or any(checksums(folder / n) != expected[n] for n in expected):
       raise SystemExit('Recovery checksum verification failed')
   for n in ('manifest.json', 'verification.json'):
       tool.decrypt_file(folder / (n + '.enc'), folder / n, key)
   manifest = check_manifest(folder)
   if not matching_receipt(folder):
       raise SystemExit('Recovery receipt invalid')
   for n in ('database.dump', 'uploads.tar.gz'):
       tool.decrypt_file(folder / (n + '.enc'), root / n, key)
       if tool.sha256_file(root / n) != manifest['artifacts'][n]['sha256']:
           raise SystemExit('Recovery plaintext verification failed')
   tool.safe_extract(root / 'uploads.tar.gz', root / 'files')
   if tool.upload_inventory(root / 'files/uploads') != manifest['uploads']['files']:
       raise SystemExit('Recovery uploads verification failed')
   print('recovery artifacts verified')
   PY
   ```

3. جهّز `.pg_service.conf` و`.pgpass` خاصين `600` في جلسة التعافي بخدمتي صيانة وهدف **للخادم الجديد** من المخزون الخاص؛ لا DSN في argv. أنشئ قاعدة جديدة وتوقف إن وجدت. أكد أن خدمة الهدف تشير إليها وللخادم الجديد قبل الكتابة.

   ```bash
   apt-get update
   apt-get install -y postgresql-client-16
   read -rp 'New recovery database name (recovery_...): ' NEW_DATABASE
   [[ "$NEW_DATABASE" =~ ^recovery_[a-z0-9_]+$ ]]
   createdb --maintenance-db=service=iorp_recovery_admin "$NEW_DATABASE"
   pg_restore --dbname=service=iorp_recovery_new --no-owner --exit-on-error --single-transaction "$RECOVERY/database.dump"
   psql service=iorp_recovery_new -X -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version'
   ```

4. انقل uploads إلى volume **جديد فقط**. أدخل صورة أدوات الاستعادة المعتمدة من السجل الخاص؛ لا socket. لا تغيّر صورة أو Compose النشر الحاليين بهذا المثال.

   ```bash
   read -rp 'Approved backup tools image reference from private inventory: ' BACKUP_IMAGE
   read -rp 'New uploads volume name (iorp-recovery-...): ' NEW_UPLOADS
   [[ "$NEW_UPLOADS" =~ ^iorp-recovery-[a-z0-9-]+$ ]]
   if docker volume inspect "$NEW_UPLOADS" >/dev/null 2>&1; then
     echo 'Recovery volume already exists; stop'; exit 1
   fi
   docker volume create "$NEW_UPLOADS"
   docker run --rm --network none --user 0 --entrypoint sh \
     --mount "type=bind,src=$RECOVERY/files/uploads,dst=/from,readonly" \
     --mount "type=volume,src=$NEW_UPLOADS,dst=/to" "$BACKUP_IMAGE" \
     -c 'cp -a /from/. /to/ && chown -R 10001:10001 /to'
   ```

5. افحص الأعداد والمرفقات وAlembic وأسرار التطبيق وMFA، واختبر التطبيق مع البريد والمهام الخارجية معطلة. تحويل التشغيل للموارد الجديدة وفتح الكتابات قرار مستقل للمالك ضمن إجراء التعافي المعتمد. احفظ الموارد السابقة؛ لا تنظيف تلقائيًا لقاعدة أو volume أو quarantine.

## التراجع وإيقاف الجدولة — خارج التسلسلات السابقة

إيقاف الإنتاج لا يحذف أي نسخ أو أسرار أو بيانات تطبيق:

```bash
sudo systemctl disable --now iorp-backup@production.timer iorp-backup-disk@production.timer
sudo systemctl stop iorp-backup@production.service iorp-backup-disk@production.service
```

لا تُفعّل staging كبديل. بعد power loss افحص الأسماء الدقيقة وlabel `iorp.purpose=backup-test` قبل تنظيف موارد الجولة بإجراء حادث منفصل؛ لا global prune ولا حذف scratch أو quarantine أثناء عملية قائمة. عند فقد المفتاح استعده من offline؛ مفتاح جديد لا يفك نسخة قديمة.
