# CUSTOMERS-UX-B

## Data and compatibility

- Geography now contains 249 countries (+235) and 357 city choices (+333):
  108 named cities and 249 country-specific Other choices. The existing 24
  Saudi city keys remain unchanged. See [sources and ordering](../data/GEOGRAPHY_SOURCES.md).
- Migration `f6a1b2p0`, after `f6a1b2o9`, invokes the missing-only standard-list
  seed for every existing organization. Names, activation flags, ordering and
  custom organization entries are never rewritten.
- `city_other` is nullable `String(120)` on customers, suppliers and customer
  sites. Writes trim and require it for an `_other` city; ordinary cities clear
  it. Changing the country without supplying a city clears the old city.
- Customer creation accepts one optional `primary_contact` object and inserts
  it as default inside the customer's transaction. Customer updates do not
  accept this object. Both customer writes stop assigning legacy phone/email.
- Reads use the default contact, including a null phone/email on that contact.
  Legacy customer phone/email are used only when no default contact exists.
  Search also matches every contact's phone and email, scoped to its customer
  and organization. Customer reports and shipping use the same read semantics.

## Migration behavior

For each customer with a nonblank legacy phone/email, migration checks existing
contacts for an exact trimmed phone **or** a case-insensitive trimmed email.
Matching either prevents creation, including inactive contacts. Phone formatting
is not guessed or rewritten. Otherwise it inserts a contact named Primary
contact for English organizations, or جهة الاتصال الرئيسية otherwise. It sets
default only when no default exists, and preserves the customer creator.

A deterministic UUID derived from organization/customer also prevents creating
a second migrated contact after an operator edits the first one's phone/email.
The original customer phone/email columns and values remain intact.

The PostgreSQL synthetic fixture has six customers and three existing contacts:
two customers match existing data, and **four** contacts are created. A direct
rerun creates **zero**; downgrade/re-upgrade also leaves seven total contacts,
including an operator-edited migrated contact. It covers a 50-character legacy
phone, a missing creator, Arabic/English names, existing defaults, inactive
customized list data, and both organizations' full catalogs.

Downgrade restores `estimated_consumption` as nullable `Numeric(14,2)` with no
values. Historical consumption is deliberately not recoverable from migration.
It drops the added location columns; take a backup before any intentional
rollback. It retains seeded catalogs and migrated contacts, which the preceding
application schema supports and which may now be edited or referenced.

## Supporting schema decisions

1. Sites previously had no country. A nullable `CustomerSite.country` supports
   the required country-first selector. Existing sites derive it from their
   catalog city's parent, then their customer country; unknown values stay null.
2. A nullable shipment `delivery_country` stores the selected site's country
   alongside its existing address/city/URL snapshot, so maps do not follow later
   edits to the customer's live address. Old shipments remain null. The printed
   delivery note and quotation PDF/templates are unchanged.
3. Customer-contact phone capacity increases from 30 to 50 to preserve every
   legacy customer phone. Customer-contact creator/updater become nullable so
   unknown historical creators remain unknown. New API writes still use the
   actor's ID. Downgrade retains these compatible widenings to avoid truncating
   phones or fabricating creators. Supplier contacts retain their existing schema.

## Validation and UI

Country/city fields, FormSection and MapLink are shared. The three new location
forms default to Saudi Arabia; changing country clears city and Other text.
The Other city name is required. MapLink uses a validated HTTPS URL or an
encoded address/city/country Google Maps search, opens a separate page with
`noopener noreferrer`, and hides without a usable URL or address. Unsafe legacy
links are not rendered, and cannot be copied into new shipment writes.

Detail grids use the existing form gap/control tokens and shrinkable columns;
badges wrap and table overflow stays inside its own scroll region. No global
overflow suppression, embedded maps or new runtime dependencies are introduced.

## Verification

- New PostgreSQL opt-in test is discovered automatically by the existing CI
  PostgreSQL integration job: `tests/test_customers_ux_migration_postgres.py`.
- The full actual Alembic chain, downgrade to `f6a1b2o9`, re-upgrade, and the
  synthetic schema migration test were exercised on isolated PostgreSQL 16.
- Backend regression tests cover atomic contact failure rollback, default
  contact fallback/search, site/supplier Other cities, HTTPS rejection, site
  snapshots and customer reporting/shipping readers.
- Frontend tests cover country/city order, disabled and filtered cities,
  clearing, Other required text, optional creation-only contacts, serialized
  contact payloads and MapLink URL safety/opening behavior.
- PR records final full backend, TypeScript, lint, frontend test, i18n and
  production build results. No operational database or deployment is modified.

## ملخص عربي

أُضيفت 235 دولة و333 خيار مدينة، بإجمالي 249 دولة و357 خيارًا، دون تغيير
مفاتيح المدن السعودية أو تخصيصات المنظمات. الترحيل `f6a1b2p0` يحافظ على
الهاتف والبريد القديمين وينقل البيانات غير المطابقة إلى جهات اتصال؛ أنشأ
اختبار PostgreSQL أربع جهات جديدة ولم ينشئ تكرارًا عند إعادة التشغيل.
إضافتا بلد الموقع وبلد لقطة الشحنة تخدمان اختيار المدينة والخرائط، دون تغيير
المستندات المطبوعة المحظورة. التراجع يعيد عمود الاستهلاك فارغًا، ويحافظ على
جهات الاتصال والقوائم وتوسعة الهاتف وسماح منشئ الاتصال التاريخي غير المعروف.
