# CUSTOMER-NAME-I18N

Base: `a14bfacbe8aa2b39b07c7feccc04bdbc51b7ffc6`; branch: `feat/customer-bilingual-name`.

## Data contract / عقد البيانات

Migration `f6a1b2p3`, after `f6a1b2p2`, adds nullable `String(255)` columns
`name_ar` and `name_en`. At least one trimmed name is required by a database
CHECK and the API (`CUSTOMER_NAME_REQUIRED`). Service writes normalize both
names and set the compatibility column `name = name_ar or name_en` on every
create/update. Existing legacy API/ORM creators using `name` remain supported;
explicit bilingual inputs take precedence. The customer name had no unique
constraint or duplicate-name check; the existing organization/code uniqueness
rule remains unchanged.

Backfill preserves the exact original value, including mixed text, and chooses
Arabic if any Arabic Unicode **letter** occurs (including presentation forms,
extended blocks and mathematical letters); Arabic punctuation/digits alone do
not classify a name as Arabic. Backfill processes keyset batches of 500.

Downgrade preserves the compatibility `name` and snapshots both languages in
`commercial_customer_name_recovery` before dropping the new columns. This table
has no public API or cross-module foreign keys. Snapshots are never automatically
deleted; a re-upgrade restores the latest matching snapshot if the legacy name
has not changed. Old-version edits are backfilled normally while their archived
alternative names remain recoverable. Protect this table like customer data.
This additional table is intentional: a single old column cannot losslessly
represent two independent names. No deployment or live migration was performed.

يحافظ `name` على توافق الوحدات الأخرى ويأخذ العربي أولًا ثم الإنجليزي. عند
التراجع يُحفظ الاسمان في جدول تعافٍ قبل حذف العمودين؛ لا فقد للاسم البديل ولا
تنظيف آلي لجدول التعافي. لا اتصال بالسيرفر ولا أسرار أو إعدادات حقيقية.

## Search and display / البحث والعرض

- Customer list, detail, create/edit, shared CustomerPicker and page headings use
  the UI locale with the other-language fallback via `customerDisplayName`.
- Commercial quotation/order/sample lists and detail headings use localized
  live customer names; shared list searches, follow-ups and order lookups match
  both names.
- Customer-report and complaint customer searches, production-demand customer
  lookups and detail/list/planning views, shipping customer lookup/picker and
  quality sample lookup searches match both names. They use existing shared
  interfaces or metadata, with no direct cross-module model import.
- Historical shipping/quality document snapshots, audit names and existing
  downstream compatibility consumers retain their stored `name` behavior.
- The customer form remains one flat grid: Arabic name, English name, then the
  original remaining fields; Arabic is RTL, English LTR. Detail shows both.

## Quotation / عرض السعر

Only the customer name chosen by the quotation builder changes. It follows the
document's language and falls back to the other customer name. The existing
document language remains the organization's `QuoteSettings.document_language`;
the existing validity-policy response also returns that language to forms.
Create/edit show a translated, nonblocking missing-name note and a customer-card
link. `attention`, `subject`, PDF templates, layout and other fields are unchanged.

## Verification / التحقق

New API/search/document tests, frontend form/helper/note tests, and a real
PostgreSQL 16 migration test cover backfill, CHECK, downgrade and re-upgrade.
The PostgreSQL tests use a disposable private schema; the local runner uses a
disposable container and generated credentials. Final command counts and CI
are recorded in the PR report.
