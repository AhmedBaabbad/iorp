# قبول مستقل لخط أساس Git — الدفعة 1.5

**التاريخ:** 2026-10-14 · **المراجع:** Claude (مستقل) · **مالك التنفيذ:** Codex
**لم يُعدَّل أي كود تطبيق ولا أي commit.** المسبار المؤقت والنسخة النظيفة حُذفا بعد الاستخدام.

## القرار: ⛔ BLOCKED

**السبب الوحيد الحاجب:** خط أساس Git المطلوب مراجعته **غير موجود**. الإصلاحات التقنية للدفعة 1.5 نفسها **سليمة ومُتحقَّق منها** (§3–§6)، والحزمة كاملة خضراء في البيئة النظيفة. يتحول القرار إلى **APPROVED WITH CONDITIONS** بمجرد إنشاء الـcommits وإعادة التحقق من checkout نظيف (§8).

---

## 1. تسلسل الـcommits والملكية — ❌ غير قابل للتحقق
```text
$ git log --all --since=2026-10-14          → (لا شيء)
$ git log -1 → 6ddd666 2026-10-11 feat(production): export customer production demands to Excel
$ git status --short | wc -l                 → 476
$ git worktree list / git stash list         → worktree واحد، لا stash
```
لا commit في أي فرع أو worktree أو stash. تقرير Codex (`docs/audits/2026-10-14-multitenant/BATCH1_5_STABILIZATION_REPORT.md` §7) يؤكد: «لا staged files ولا commit لهذه الدفعة»، مع نقطتي حفظ محليتين في `.tmp/` (ليستا بديلًا عن Git).

## 2. الملفات المحذوفة سهوًا / حفظ العمل غير المرتبط — ⚠️ جزئي
- **حفظ العمل:** لا `reset` ولا حذف؛ الـ462→476 تغييرًا باقية في شجرة العمل. ✅
- **الإغفال:** لا يمكن الحكم دون commits. نقطة الحفظ الختامية تحوي 203 ملفات غير متتبعة بلا `.env` ولا dumps (تحققت بفتح الأرشيفين). ✅

## 3. إمكانية الإعادة من checkout نظيف — ❌ تفشل (دليل)
```text
git archive HEAD backend | tar -x   (نسخة نظيفة مؤقتة) + نسخ ملفات الدفعة 1/1.5 فقط
pytest --co tests/test_route_inventory.py tests/security tests/test_batch1_isolation.py tests/core/test_backup_tool.py
→ ImportError while loading conftest … ModuleNotFoundError: No module named 'app.notifications'
```
اختبارات الدفعة 1/1.5 تعتمد على وحدات غير متتبعة في Git (`app/notifications`، أدلة الشحن، التفويضات، `core/files.py`، سياسات الحساب). **هذا هو العائق الحرج.**

## 4. اكتشاف المسارات واختبارات التفويض الفاشلة عند الخطأ — ✅ مُتحقَّق
- `tests/route_inventory.py`: يجمع المسارات عبر `effective_candidates` (FastAPI 0.143) ويحتفظ بالبادئة والاعتماديات الموروثة؛ **يفشل** تحت 450 مسارًا، ويرفض `Mount` وأي تمثيل كسول غير معروف، ويقارن بـ OpenAPI غير المخبّأ. سجل `route_inventory_registry.json` (485 زوجًا) يفشل عند أي إضافة/إزالة غير مراجعة.
- **اختبار حقن مستقل (Fail-closed):** أضفتُ مؤقتًا مسارًا غير محمي `GET /api/v1/zz-probe/items/{item_id}` ثم شغّلت حراس التفويض والجرد:
```text
FastAPI 0.143.1 (البيئة النظيفة):  2 failed, 422 passed
  test_all_route_authorization.py:55  AssertionError: ['/api/v1/zz-probe/items/{item_id}']
  route_inventory.py:65               RuntimeError: Route registration review required: added=['GET /api/v1/zz-probe/items/{item_id}']
FastAPI 0.115.0 (المفسّر القديم):   2 failed, 422 passed  (نفس الرسالتين)
```
  ثم حُذف المسبار. **الحراس لم تعد تنجح فارغة على أي من النسختين.**
- مسارا تغيير البريد أُضيفا إلى `PUBLIC_OR_SELF` — متوافق مع فحصي السابق (مستخدم مسجل + كلمة مرور/رمزان + تحديد معدل).

## 5. تغطية انحدار العزل — ✅ مع حدود معلنة
- المسح (71 مسارًا، 8 وحدات) صار يعتمد على الاكتشاف الصحيح؛ والحالات الثلاث التي وجدتُها يدويًا صارت دائمة في `tests/security/test_cross_tenant_additional.py` (فلاتر الاستعلام، PATCH بمراجع أجنبية، معاينة/PDF التقارير).
- **حدود صحيحة الإعلان في تقرير Codex:** 214 عملية بمعرّف (209 موارد منظمة + 5 ديناميكية) مسجلة في الجرد لكن **بلا اختبار عزل سلوكي آلي**؛ بعض ردود 422 في المسح العام تسبق فحص المورد فلا تُحتسب دليلًا. لا ادعاء لعزل شامل.

## 6. تصحيحات النسخ والاستعادة — ✅ مُتحقَّق
| التصحيح | التحقق المستقل |
|---|---|
| `recovery_drill.py`: `RuntimeError` بدل `assert` + اختبار تحت `python -O` | ضمن 31 ناجحًا |
| تشفير متدفق (`BackupSink`) — لا dump صريح على القرص | `test_streamed_encryption_roundtrip_without_plaintext_file` ✅ |
| رفض الإطارات المبتورة/الطول غير الآمن، مسارات artifacts الخارجية، الوجهة الموجودة | ✅ |
| `prune` يتحقق من كل النسخ ويشترط إيصال استعادة ناجحًا مرتبطًا ببصمة manifest، ويحفظ الأحدث حتى مع 0/0/0 | ✅ (فساد/غياب إيصال/تغيّر manifest ← لا حذف) |
| `verify` لا يعود لقاعدة التطبيق: يلزم `IORP_RESTORE_DATABASE_URL` و`IORP_RESTORE_SCRATCH`؛ `--single-transaction` | ✅ |
| **تمرين حقيقي مستقل** على حاوية PostgreSQL مؤقتة ببيانات اصطناعية: `RUN_BACKUP_CONTAINER_TESTS=1 pytest tests/test_backup_roundtrip_isolated.py` | **1 passed**؛ لا حاوية متبقية (`docker ps -a --filter label=iorp.purpose` فارغ) |

```text
pytest tests/core/test_backup_tool.py tests/test_backup_roundtrip_isolated.py tests/test_recovery_drill.py
→ 31 passed, 1 skipped (الـopt-in) ؛ ثم مع الـopt-in → 1 passed
```
**ملاحظة غير حاجبة (N-1):** شرط «هدف معزول» في `verify` يتحقق من **اسم القاعدة** فقط (`iorp_restore_verify_*`) لا من **الخادم** — يمكن تمرير رابط بنفس مضيف/منفذ قاعدة الإنتاج. يُستحسن رفض الهدف إذا طابق مضيف ومنفذ `DATABASE_URL`.

## 7. الاختبارات المتخطاة والفشل المتبقي — ✅
```text
البيئة النظيفة (FastAPI 0.143.1 / Starlette 0.52.1)، APP_ENV=test، DATABASE_URL→127.0.0.1:1 (غير قابل للوصول):
pytest -q -rfs     → 2379 passed, 0 failed, 57 skipped, 1 xfailed   (31:45)
frontend: vitest   → 272 passed (49 files)   ·   node --test → 87/87   ·   tsc → نظيف
```
| سبب التخطي | العدد | حكم |
|---|---:|---|
| PostgreSQL opt-in (ترحيلات، تخصيص، readiness) | 40 | مشروع، **لكن سلسلة الترحيلات غير مُختبرة في هذا التشغيل** |
| عارض التقارير/Chromium/عينات | 16 | مشروع |
| تمرين Docker opt-in | 1 | شُغّل يدويًا ونجح |

لا skip يخفي فشلًا.

## 8. الأسرار — ✅
- فحص كل الملفات المعدلة/غير المتتبعة غير المتجاهلة بأنماط (مفاتيح خاصة، AWS/GitHub/OpenAI/Slack، `SECRET_KEY|SMTP_PASSWORD|IORP_BACKUP_KEY|PASSWORD|TOKEN = قيمة طويلة`): **لا نتائج**.
- `backend/.env` و`frontend/.env` و`.tmp/` متجاهلة؛ لا `.env`/`.pem`/`.key`/dump مرشح للـcommit؛ تعديلات `.env.example` بلا قيم سرية.
- **حد:** الفحص على شجرة العمل لا على commits (غير موجودة)؛ يُعاد على الـcommits النهائية.

## 9. الجاهزية للدفعة 2

### العوائق (Blockers) — يجب إغلاقها
| # | العائق | الإصلاح المطلوب | المالك |
|---|---|---|---|
| B-1 | لا خط أساس Git | commits منطقية بالترتيب المقترح في تقرير Codex §7: (1) الميزات التشغيلية غير المحفوظة بحسب أصحابها، (2) ADR-010 والوحدات مع اختباراتها، (3) الدفعة 1، (4) الدفعة 1.5 | Codex + أصحاب الميزات |
| B-2 | الإعادة من checkout نظيف تفشل | بعد B-1: `git worktree add` نظيف ← تثبيت من `evidence/python-baseline-lock.txt` ← الحزمة كاملة + الواجهة | Codex، ثم إعادة تحقق Claude |

### شروط غير حاجبة (بعد رفع الحجب)
1. **N-1:** رفض هدف الاستعادة إذا طابق مضيف/منفذ قاعدة التطبيق.
2. **N-2:** تشغيل اختبارات PostgreSQL الـ40 (بما فيها سلسلة الترحيلات) مرة واحدة على حاوية معزولة وإرفاق النتيجة.
3. **N-3:** الـ214 عملية بلا عزل سلوكي آلي تبقى مسجلة كمخاطر مقبولة مؤقتًا، مع خطة توسيع المسح (المبيعات/الإنتاج/الجودة/الإدارة).
4. **N-4:** تثبيت حد أعلى مُختبر لـ FastAPI/Starlette أو اعتماد ملف القفل رسميًا قبل أي ترقية.
5. **N-5:** إعادة فحص الأسرار على الـcommits النهائية.

**لا موافقة على النشر للإنتاج. لا بدء للدفعة 2 أو 3.**
