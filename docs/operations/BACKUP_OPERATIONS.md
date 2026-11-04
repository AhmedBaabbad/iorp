# تشغيل النسخ الاحتياطي لـ IORP — المرحلة هـ

الحالة: تنفيذ للمراجعة؛ **production معطلة حتى اعتماد Claude**. لا تثبت هذه الوثيقة تنفيذ خطوات على VPS. تُنفّذ خطوات staging أدناه كلها بالترتيب، ثم تُرفق نتائج التشغيل اليدوي وموعد timer الفعلي واختبار الفشل بالمراجعة. لا يوجد timer أسبوعي: التحقق اليومي من نسخة منزّلة هو تمرين الاسترجاع.

## حدود التشغيل المعتمدة

- المسار اليومي تحت `flock` غير منتظر، مشترك بين البيئتين والتشغيل اليدوي: جمع مشفر → رفع → تنزيل → SHA-256 → استعادة إلى PostgreSQL مؤقت → receipt → احتفاظ → Push. لا socket أو Docker CLI في حاويات التطبيق/النسخ. Docker وrclone وPython coordinator على المضيف فقط.
- جمع النسخة على شبكة `db` فقط وuploads للقراءة. verify على المضيف، إلى حاوية منفصلة على bridge مخصص (بلا انضمام لشبكات التطبيق)، label `backup-test` وID كامل ومنفذ loopback عشوائي وبلا bind mounts. لا تُمرر بيانات اعتماد الإنتاج إلى PostgreSQL المؤقت. تُحفظ حراسات `verify` كما هي.
- **لا تجميد كتابة في v1.** لقطة DB أولًا، ثم inventory وأرشفة المرفقات. `referenced_but_missing` غير الفارغة تعني إعادة جمع واحدة فقط، ثم فشل وتنبيه؛ لا رفع أو اعتماد النسخة الناقصة. تغيّر الملفات بين inventory وtar قد يُفشل verify أيضًا. لا ضمان لقطة ذرية مشتركة أو PITR.
- فحص `9134fd9`: `LocalFileStorage.delete` يحذف فعليًا. الشحن يحذف بعد commit، واستبدال الشعار يولّد مفتاح UUID جديدًا ثم يتخلص من القديم. `put` نفسه يستخدم `write_bytes` ويمكنه تقنيًا استبدال مفتاح قائم، لكن لم يوجد caller إنتاجي يعيد استخدام المفتاح في مسارات الرفع الحالية (`files.store` وprovisioning). إضافة caller يعيد استخدام مفتاح تستلزم إعادة مراجعة الاتساق قبل الاعتماد.
- v1 تستخدم **حساب التطبيق** من نسخة env مستقلة تحوي `DATABASE_URL` فقط. دين تقني: reader مخصص بعد اختبار GRANT للموجود وALTER DEFAULT PRIVILEGES لكل مالك ينشئ الجداول وsequences المستقبلية. الجمع ينفّذ SELECT وpg_dump فقط؛ عدد جداول public في TOC للـdump يجب أن يساوي `pg_tables`، ويتحقق restore من الأعداد والمرفقات وAlembic.
- scratch مجلد قرص خاص `700` يملكه root، حساب خدمة التنسيق الإدارية. مخرجات حاوية الجمع `700` بمالك `10001`. بيانات PostgreSQL على Docker volume مؤقت بلا bind mount، بصلاحيات PostgreSQL الخاصة. يُحذف scratch والحاوية والvolume والشبكة في `finally` عند النجاح والفشل وSIGTERM/SIGINT. لا ضمان trap عند انقطاع الكهرباء أو SIGKILL؛ وجود scratch قديم يمنع الجولة التالية حتى التحقيق. حذف SSD ليس مسحًا آمنًا. لا اشتراط swap مشفر: القاعدة الحية أصلًا غير مشفرة على القرص نفسه، حسب قرار المراجعة.
- الحدود الافتراضية: جمع 512MiB/0.5CPU؛ PostgreSQL مؤقت 768MiB/0.5CPU دون swap؛ منسّق 768MiB/50% CPU وأولوية I/O منخفضة. scratch وPG كل منهما 8GiB، مساحة حرة دنيا 2GiB، مهلة 7200 ثانية، نقل 8MiB/s. فحص دوري للحجم أثناء العمليات؛ هذه حدود إيقاف مراقبة وليست filesystem quota ذرية، وقد تتجاوزها الكتابة بين فحصين. `LimitFSIZE=10G` حد إضافي لملفات عمليات المضيف، لا لحاويات Docker. تُقاس الأحجام على staging قبل إنتاج فعلي؛ لا تعدّل nexus أو cron التنظيف.
- محليًا أحدث 3 نسخ ناجحة؛ خارجيًا اتحاد أحدث نسخة لكل 7 أيام و4 أسابيع ISO و6 أشهر UTC، مع حماية أحدث نسخة متحقق منها. التحقق اليومي يعيد فحص محتوى مرشحي الاحتفاظ الخارجيين قبل الحذف (تكلفة تنزيل إضافية يجب قياسها). لا حذف عند فشل الرفع/الاستعادة؛ قد يتجاوز العدد السياسة مؤقتًا. مجلد رفع بلا `complete.enc` غير معتمد، يُترك للتحقيق ولا يُحذف آليًا. لا `rclone sync` أو purge للمجلد الأب.
- ملفات Drive الوحيدة: dump وuploads وmanifest وreceipt وعلامة الإتمام، كلها مشفرة. لا manifest واضح خارج المضيف. سجلات journal ثابتة بلا أسرار؛ لا `set -x`، ولا طباعة env أو `docker inspect` كاملًا أو stderr الخام. root/Docker وصول إداري؛ لا تمنح صلاحيات تعديل source أو config لمستخدمي التطبيق.

## تسلسل التثبيت والتحقق على staging

الأوامر Bash على VPS بحساب `rehanh` إلا حيث يذكر جهاز المالك. استبدل `VPS_HOST` بالعنوان المحفوظ خارج Git. توقف عند أي فشل. SHA أدناه إصدار راجعه Claude ونجح CI ونُشرت صوره في GHCR؛ نشر الصور الحالي يتم عند push إلى main فقط، لذلك لا تُفعّل هذه الخطوات بصورة فرع غير منشورة. تبقى production خارج هذا التسلسل.

1. على VPS، عرّف المتغيرات وثبّت أدوات المضيف. لا تُغيّر تطبيقات الخادم الأخرى.

   ```bash
   set -euo pipefail
   umask 077
   ENVIRONMENT=staging
   BASE=/opt/apps/iorp/$ENVIRONMENT
   read -rp 'Approved published release SHA (40 hex): ' RELEASE_SHA
   [[ "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]
   sudo apt-get update
   sudo apt-get install -y python3-venv rclone git
   sudo install -d -m 700 "$BASE/backups" "$BASE/backup-runtime"
   sudo install -d -m 700 -o rehanh -g rehanh "$BASE/env"
   sudo install -d -m 700 "$BASE/env/rclone"
   ```

2. ثبّت source مطابقًا للإصدار وvenv باعتماديات مقفلة. لا تنسخ أسرارًا إلى source. تأكد أن staging نفسها نُشرت بالإصدار المعتمد عبر إجراء النشر المعتاد قبل استكمال الخطوة.

   ```bash
   sudo git clone https://github.com/AhmedBaabbad/iorp.git "$BASE/backup-runtime/source"
   sudo git -C "$BASE/backup-runtime/source" checkout --detach "$RELEASE_SHA"
   SOURCE=$BASE/backup-runtime/source
   sudo python3 -m venv "$BASE/backup-runtime/venv"
   sudo "$BASE/backup-runtime/venv/bin/pip" install --require-hashes --no-deps -r "$SOURCE/backend/requirements.lock"
   PY=$BASE/backup-runtime/venv/bin/python
   OPS=$SOURCE/backend/scripts/backup/ops_backup.py
   sudo install -m 644 "$SOURCE/deploy/compose.yaml" "$BASE/compose.yaml"
   sudo install -o root -g root -m 600 "$SOURCE/deploy/env/backup-ops.env.example" "$BASE/env/backup-ops.env"
   sudo install -o rehanh -g rehanh -m 600 "$SOURCE/deploy/env/backup-database.env.example" "$BASE/env/backup-database.env"
   sudo install -o rehanh -g rehanh -m 600 "$SOURCE/deploy/env/backup-push.env.example" "$BASE/env/backup-push.env"
   ```

3. أدخل الرابط من backend.env إلى `backup-database.env` فقط، وضع **ثلاثة** Push URLs في الملف المخصص. في Kuma: daily وrestore مهلة 93600 ثانية (26 ساعة)، وdisk مهلة 1200 ثانية؛ فعّل قنوات التنبيه واختبر وصولها. افتح إعدادات غير سرية واضبط المسارات الفعلية لملف Compose env، ويجب أن يحمل `IORP_IMAGE_TAG` نفس SHA. اترك `PRODUCTION_APPROVED=no`، واضبط `ENABLED=yes` لـstaging فقط. لا تطبع الملفات.

   ```bash
   nano "$BASE/env/backup-database.env"
   nano "$BASE/env/backup-push.env"
   sudoedit "$BASE/env/backup-ops.env"
   nano "$BASE/env/staging.env"
   chmod 600 "$BASE/env/backup-database.env" "$BASE/env/backup-push.env"
   ```

4. على VPS، أنشئ rclone remote باسم `iorpdrive`: اختر Drive وscope **drive.file** فقط، وOAuth client ثابت يملكه المالك (حالة نشر تسمح بتفويض طويل العمر)، وأجب No للمتصفح. عند طلب التفويض، انتقل للخطوة 5 واترك الجلسة مفتوحة. لا توسّع scope لحل خطأ وصول.

   ```bash
   sudo rclone config --config "$BASE/env/rclone/rclone.conf"
   ```

5. على **جهاز المالك** المثبت عليه rclone، شغّل أمر `rclone authorize` الذي عرضته جلسة الإعداد، بنفس client ID وscope blob، وأكمل الدخول بالمتصفح؛ انقل الناتج إلى prompt الجلسة في الخطوة 4 دون حفظه في سجل/محادثة. ثم على VPS أكمل:

   ```bash
   sudo chmod 600 "$BASE/env/rclone/rclone.conf"
   sudo rclone --config "$BASE/env/rclone/rclone.conf" mkdir "iorpdrive:iorp-backups/staging"
   ```

6. على VPS ولّد المفتاح مباشرة إلى ملف، وجهّز مواد التعافي دون عرضها. ملفات env هنا بصيغة `NAME=value`؛ لا shell expansion أو multiline. لا تدوّر المفتاح بحذف القديم؛ النسخ السابقة تحتاجه طوال مدة الاحتفاظ.

   ```bash
   sudo "$PY" - "$BASE" "$SOURCE" <<'PY'
   import os, sys
   from pathlib import Path
   sys.path.insert(0, sys.argv[2] + '/backend/scripts/backup')
   from ops_backup import read_env
   from cryptography.fernet import Fernet
   base = Path(sys.argv[1]); os.umask(0o077)
   keyfile = base / 'env/backup-key.env'
   with keyfile.open('x') as f:
       f.write('IORP_BACKUP_KEY=' + Fernet.generate_key().decode() + '\n')
   app = read_env(base / 'env/backend.env')
   recovery = read_env(keyfile)
   for name in ('SECRET_KEY', 'PLATFORM_MFA_KEYS'):
       if not app.get(name):
           raise SystemExit('Missing recovery material')
       recovery[name] = app[name]
   with (base / 'env/recovery.env').open('x') as f:
       f.write(''.join(k + '=' + v + '\n' for k, v in recovery.items()))
   PY
   sudo chown rehanh:rehanh "$BASE/env/backup-key.env" "$BASE/env/recovery.env"
   chmod 600 "$BASE/env/backup-key.env" "$BASE/env/recovery.env"
   ```

7. على **جهاز المالك**، احفظ `recovery.env` في مخزن offline مشفر مستقل عن VPS وDrive، باسم يحدد البيئة. يشمل `IORP_BACKUP_KEY` و`SECRET_KEY` و`PLATFORM_MFA_KEYS` لكل بيئة. احتفظ أيضًا بإعدادات الإصدار وطريقة الوصول الطارئ. اختبر فتح المخزن، ثم استخرج منه نسخة الاختبار وأعدها للخادم باسم مختلف؛ لا تعتمد على نسخة لا تزال في cache أو في Downloads فقط.

   ```bash
   umask 077
   scp rehanh@VPS_HOST:/opt/apps/iorp/staging/env/recovery.env ./iorp-staging-recovery.env
   # احفظ الملف في مخزنك offline المشفر ثم استخرج النسخة المحفوظة فعليًا إلى هذا المسار.
   scp ./iorp-staging-recovery.env rehanh@VPS_HOST:/opt/apps/iorp/staging/env/recovered-offline.env
   ```

8. على VPS، نفّذ النسخة اليدوية الأولى بالمفتاح الأصلي، ثم استخرج مفتاح النسخة المحفوظة offline إلى ملف خاص، واستخدمه في **تمرين منفصل على النسخة الموجودة أصلًا في Drive**. نجاح جمع نسخة جديدة بالمفتاح المستعاد وحده لا يثبت فك النسخة السابقة.

   ```bash
   sudo "$PY" "$OPS" daily --config "$BASE/env/backup-ops.env"
   sudo "$PY" - "$BASE" "$SOURCE" <<'PY'
   import os, sys
   from pathlib import Path
   sys.path.insert(0, sys.argv[2] + '/backend/scripts/backup')
   from ops_backup import read_env
   base = Path(sys.argv[1]); os.umask(0o077)
   recovered = read_env(base / 'env/recovered-offline.env')
   original = read_env(base / 'env/recovery.env')
   if any(recovered.get(k) != original[k] for k in original):
       raise SystemExit('Offline recovery material does not match')
   (base / 'env/recovered-key.env').write_text('IORP_BACKUP_KEY=' + recovered['IORP_BACKUP_KEY'] + '\n')
   config = (base / 'env/backup-ops.env').read_text()
   config = config.replace('KEY_ENV_FILE=' + str(base / 'env/backup-key.env'), 'KEY_ENV_FILE=' + str(base / 'env/recovered-key.env'))
   (base / 'env/backup-offline-test.env').write_text(config)
   PY
   sudo "$PY" "$OPS" drill --config "$BASE/env/backup-offline-test.env"
   sudo test -n "$(sudo find "$BASE/backups/manual-receipts" -name '*.json' -print -quit)"
   rm -- "$BASE/env/recovery.env" "$BASE/env/recovered-offline.env"
   ```

9. ثبّت وحدات systemd وفعّل **staging فقط**. انتظر التشغيل الفعلي التالي 23:30 UTC، وليس `start service` بديلًا عنه. افحص الوقت والنتيجة وreceipt ووصول Push وسلامة nexus. لا تبدأ production.

   ```bash
   for unit in iorp-backup@.service iorp-backup@.timer iorp-backup-disk@.service iorp-backup-disk@.timer; do
     sudo install -m 644 "$SOURCE/deploy/backup/$unit" /etc/systemd/system/
   done
   sudo systemctl daemon-reload
   sudo systemctl enable --now iorp-backup@staging.timer iorp-backup-disk@staging.timer
   systemctl list-timers 'iorp-backup*'
   # بعد موعد التشغيل الفعلي التالي:
   sudo systemctl show iorp-backup@staging.service -p Result -p ExecMainStatus -p ExecMainStartTimestamp
   sudo journalctl -u iorp-backup@staging.service --since yesterday --no-pager
   ```

10. اختبر الفشل المقصود عبر config مستقل بremote غير موجود، دون تغيير إعداد الجولة السليمة. يجب أن يفشل، ويصل daily=down فورًا، ولا يُضاف receipt أو تُحذف أي نسخة معتمدة. قارن قائمة معرفات النسخ قبل/بعد (لا تطبع محتواها).

    ```bash
    sudo "$PY" - "$BASE" <<'PY'
    import os, sys
    from pathlib import Path
    base = Path(sys.argv[1]); os.umask(0o077)
    text = (base / 'env/backup-ops.env').read_text()
    (base / 'env/backup-failure.env').write_text(text.replace('RCLONE_REMOTE=iorpdrive', 'RCLONE_REMOTE=deliberately_missing'))
    PY
    sudo find "$BASE/backups/local" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort > /tmp/iorp-before.txt
    if sudo "$PY" "$OPS" daily --config "$BASE/env/backup-failure.env"; then
      echo 'Unexpected success; staging gate failed'; exit 1
    fi
    sudo find "$BASE/backups/local" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort > /tmp/iorp-after.txt
    diff /tmp/iorp-before.txt /tmp/iorp-after.txt
    sudo test ! -e "$BASE/backups/scratch"
    ```

11. استعد حالة المراقبة بتشغيل يدوي ناجح، وسجّل الدليل: SHA، الزمن، الحجم، سلامة المرفقات وAlembic، receipts، وقت timer الفعلي، down عند remote الخطأ، وتنبيه القرص (>80% يُغطى باختبار وحدات؛ لا تملأ قرص VPS عمدًا). ارفع الأدلة بعد حذف أي أسرار لمراجعة Claude. توقف هنا: **لا enable لـproduction قبل الاعتماد**.

    ```bash
    sudo "$PY" "$OPS" daily --config "$BASE/env/backup-ops.env"
    sudo "$PY" "$OPS" disk --config "$BASE/env/backup-ops.env"
    sudo journalctl -u iorp-backup@staging.service --since yesterday --no-pager
    ```

## التفعيل الإنتاجي بعد اعتماد منفصل

ينفّذ المالك التسلسل السابق بمسارات production ومفاتيح وDrive ومراقبات مستقلة، بعد نجاح أدلة staging واعتماد Claude. في config الإنتاج يظل `ENABLED=no` و`PRODUCTION_APPROVED=no` حتى ذلك القرار؛ لا توجد مهمة تثبيت تفعّلهما. عند الاعتماد فقط يغيّر المالك القيمتين إلى yes، ويثبت الوحدات ويفعّل مثيلي production. لا تعمل staging بالتوازي معها؛ القفل مشترك. لا تنسخ بيانات production الحقيقية إلى staging.

## الاسترجاع الفعلي إلى production — إجراء طوارئ متعمد مستقل

هذا إجراء منفصل لا ينفّذه timer أو `verify`. يحتاج قرار المالك بقبول فقد كتابات ما بعد النسخة ونافذة صيانة. لا تستخدم `--clean` أو DROP على القاعدة الحالية. الهدف موارد **جديدة** ثم تحويل التشغيل بعد التحقق. يجب توفر نسخة source وCompose وأسرار التطبيق والمفتاح من المخزن offline.

1. أوقف الكتابات والمهام عبر إجراء النشر المعتمد، وحدد مع المالك معرف النسخة المكتملة على Drive وهدف PostgreSQL 16 جديدًا وvolume uploads جديدًا. قبل أي استرجاع، نفّذ `drill` أعلاه بالمفتاح المستعاد وconfig البيئة المعتمدة؛ احتفظ بالreceipt. الأوامر المتبقية في جلسة root إدارية خاصة حتى تكون ملكية ملفات التعافي وملفات اتصال PostgreSQL واحدة.

   ```bash
   sudo -i
   set -euo pipefail
   umask 077
   apt-get update
   apt-get install -y postgresql-client-16
   ```
2. نزّل المجلد المحدد إلى مساحة تعافٍ خاصة، وافك الشيفرة وافحص **كل** بصمات completion والmanifest قبل استخراج البيانات. ملف `recovery.env` الآتي مستعاد offline بصلاحية 600. غيّر `BACKUP_ID` إلى المعرف الذي اعتمده المالك.

   ```bash
   umask 077
   RECOVERY=/opt/apps/iorp/production/recovery
   read -rp 'Owner-approved completed backup ID: ' BACKUP_ID
   [[ "$BACKUP_ID" =~ ^iorp-[0-9]{8}T[0-9]{6}Z$ ]]
   mkdir -m 700 "$RECOVERY"
   sudo rclone --config /opt/apps/iorp/production/env/rclone/rclone.conf copy "iorpdrive:iorp-backups/production/$BACKUP_ID" "$RECOVERY/sealed"
   sudo /opt/apps/iorp/production/backup-runtime/venv/bin/python - "$RECOVERY" <<'PY'
   import json, sys
   from pathlib import Path
   sys.path.insert(0, '/opt/apps/iorp/production/backup-runtime/source/backend/scripts/backup')
   import iorp_backup as tool
   from ops_backup import read_env, check_manifest, matching_receipt, PAYLOADS
   root = Path(sys.argv[1]); folder = root / 'sealed'
   key = read_env(Path('/opt/apps/iorp/production/env/recovery.env'))['IORP_BACKUP_KEY']
   tool.decrypt_file(folder / 'complete.enc', folder / 'complete.json', key)
   expected = json.loads((folder / 'complete.json').read_text())
   if set(expected) != {*PAYLOADS, 'verification.json.enc'}:
       raise SystemExit('Invalid completion record')
   if any(tool.sha256_file(folder / name) != expected[name] for name in expected):
       raise SystemExit('Ciphertext checksum mismatch')
   for name in ('manifest.json', 'verification.json'):
       tool.decrypt_file(folder / (name + '.enc'), folder / name, key)
   check_manifest(folder)
   if not matching_receipt(folder):
       raise SystemExit('Missing verified recovery receipt')
   manifest = json.loads((folder / 'manifest.json').read_text())
   for name in ('database.dump', 'uploads.tar.gz'):
       tool.decrypt_file(folder / (name + '.enc'), root / name, key)
       if tool.sha256_file(root / name) != manifest['artifacts'][name]['sha256']:
           raise SystemExit('Plaintext checksum mismatch')
   tool.safe_extract(root / 'uploads.tar.gz', root / 'restored-files')
   if tool.upload_inventory(root / 'restored-files/uploads') != manifest['uploads']['files']:
       raise SystemExit('Uploads mismatch')
   PY
   ```

3. جهّز خدمة `iorp_recovery_admin` على **خادم PostgreSQL الجديد** بحساب مالك/ترحيل معتمد، وخدمة `iorp_recovery_new` على الخادم نفسه بقاعدة `iorp_recovered_new`؛ اكتب الاتصال في `/root/.pg_service.conf` وكلمات المرور في `/root/.pgpass`. تأكد يدويًا أن host مختلف عن خادم القاعدة الحالية. إنشاء القاعدة التالية يجب أن يفشل إن كانت موجودة؛ لا تعالج ذلك بحذفها. لا تغيّر `verify` ليستهدف production.

   ```bash
   nano /root/.pg_service.conf
   nano /root/.pgpass
   chmod 600 /root/.pg_service.conf /root/.pgpass
   createdb --maintenance-db=service=iorp_recovery_admin iorp_recovered_new
   pg_restore --dbname=service=iorp_recovery_new --no-owner --exit-on-error --single-transaction "$RECOVERY/database.dump"
   ```

4. انقل `restored-files/uploads` إلى volume **جديد** بملكية `10001:10001`. الصورة من SHA النسخة المعتمدة والمحفوظ offline، ولا تضم socket. افحص Alembic ثم طابق أعداد الجداول والمرفقات ومواد MFA واختبر التطبيق مع البريد والمهام الخارجية معطلة. لا تُحوّل الزيارات حتى نجاح فحوص الأعمال والمالك. حدّث إعداد DB وuploads إلى الموارد الجديدة عبر إجراء النشر، ثم readiness وsmoke وفتح الكتابات والمراقبة. احتفظ بالموارد السابقة وفق قرار الحادث؛ لا تنظيف تلقائي لها.

   ```bash
   read -rp 'Approved recovery image SHA (40 hex): ' RECOVERY_SHA
   [[ "$RECOVERY_SHA" =~ ^[0-9a-f]{40}$ ]]
   read -rp 'New uploads volume name (iorp-recovery-...): ' NEW_UPLOADS
   [[ "$NEW_UPLOADS" =~ ^iorp-recovery-[a-z0-9-]+$ ]]
   if docker volume inspect "$NEW_UPLOADS" >/dev/null 2>&1; then
     echo 'Volume already exists; stop'; exit 1
   fi
   docker volume create "$NEW_UPLOADS"
   docker run --rm --network none --user 0 --entrypoint sh \
     --mount "type=bind,src=$RECOVERY/restored-files/uploads,dst=/from,readonly" \
     --mount "type=volume,src=$NEW_UPLOADS,dst=/to" \
     "ghcr.io/ahmedbaabbad/iorp/backup:$RECOVERY_SHA" \
     -c 'cp -a /from/. /to/ && chown -R 10001:10001 /to'
   psql service=iorp_recovery_new -X -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version'
   ```

## التراجع والتنظيف الطارئ — خارج التسلسل أعلاه

إيقاف الجدولة لا يحذف نسخًا أو بيانات:

```bash
sudo systemctl disable --now iorp-backup@staging.timer iorp-backup-disk@staging.timer
sudo systemctl stop iorp-backup@staging.service
```

عند بقايا power loss: أوقف الخدمة، وافحص فقط الأسماء `iorp-backup-verify-*` و`iorp-backup-collect-*` المسجلة في Docker والتوقيت، وتأكد من label `iorp.purpose=backup-test` قبل حذف موارد التمرين بأسمائها الدقيقة. لا global prune ولا حذف volume للقاعدة الحية. تحقق من عدم وجود مهمة شغالة قبل حذف مجلد scratch المحدد؛ لا تمس `local` أو Drive. نجاح تنظيف الخدمة شرط للـdaily Push؛ تحقق يدويًا عند انقطاع daemon.

تعطيل production بعد تفعيلها، إن لزم، يستخدم مثيلي production بالأسماء نفسها في إجراء تراجع مستقل معتمد. لا تعيد ملف Compose قديمًا فوق نشر حي دون مراجعة توافقه. عند فقد المفتاح لا تدوّر فوق النسخ القديمة: استرجع المفتاح offline أولًا. أسرار Drive قابلة للتجديد؛ مفتاح تشفير نسخة مفقود غير قابل للتعويض.
