# Commercial sample properties

Master Data is the single definition source: organization-scoped Product key → Product.properties → Sample property values. Commercial uses the public `core/interfaces/product_catalog.py` provider; it does not import Master Data persistence or maintain product-specific fields.

## API and storage compatibility

- `GET /api/v1/commercial/samples/product-options` returns the organization's active products and property templates. It requires sample read, create, or update permission; it does not grant Master Data write access.
- Create and PATCH accept `product_type` (the existing immutable Master Data product key) and `property_values` (key/value mapping). Existing clients may still send `requested_spec_json`; sending both aliases is rejected.
- Sample detail returns `product_definition` and `property_values`, retaining `requested_spec_json` for compatibility. The UI never edits or displays raw JSON.
- Existing storage remains `Sample.product_type` and `Sample.requested_spec_json`; `property_values` is an API alias, not a second store. No new migration, bulk conversion, or data deletion is required. The existing Master Data migrations remain prerequisites.

## Validation and historical records

New samples require an existing active product belonging to the authenticated organization, including when its catalog is empty. Values are validated against that product's current property keys, required flags, number/text/choice kinds and configured choice options. Numbers must be finite and cannot be booleans. Units and localized labels come from Master Data. No Commercial-specific product rules are present.

An unchanged historical product/specification can remain during notes/status edits. Unknown historical product names are not guessed or silently mapped. Editing specifications requires a valid product and current schema. Retired property keys on that same sample are preserved, including when omitted by the client, but cannot be added or changed. Explicitly selecting a different product starts a new property mapping. Inactive existing products retain their template on edit.

Current Master Data supports required flags and choice options, but does not define numeric ranges or regex rules; this change does not invent additional constraints or schema snapshots. Template changes apply to subsequent specification edits.

Read-only inspection of the development database on 2026-10-06 found one Master Data product and zero samples. Legacy compatibility is therefore covered by synthetic persisted samples in `backend/tests/commercial/test_sample_properties.py`, including unknown products, nested values, and retired properties.

## Verification

- Backend: sample property API tests, existing sample/evaluation tests, Master Data tests, module boundary tests.
- Frontend: dynamic schema fields, typed submission, saved values, product switches, empty/failing catalog, legacy preservation, inactive products and readable detail values.
- TypeScript, targeted ESLint and localization checks.

## Files changed for this feature

Backend:
- `backend/app/core/interfaces/product_catalog.py`
- `backend/app/masterdata/application/catalog_provider.py`
- `backend/app/masterdata/domain/rules.py`
- `backend/app/commercial/api/schemas.py`
- `backend/app/commercial/api/routes_samples.py`
- `backend/app/commercial/application/sample_service.py`

Frontend:
- `frontend/src/features/samples/components/SampleProperties.tsx`
- `frontend/src/features/samples/components/SampleForm.tsx`
- `frontend/src/features/samples/components/SampleEditForm.tsx`
- `frontend/src/features/samples/components/SampleDetail.tsx`
- `frontend/src/features/samples/components/sample-errors.ts`
- `frontend/src/features/samples/api/samples-api.ts`
- `frontend/src/features/samples/types/index.ts`
- `frontend/src/i18n/locales/ar/commercial.json`
- `frontend/src/i18n/locales/en/commercial.json`

Tests and documentation:
- `backend/tests/commercial/test_sample_properties.py`
- `backend/tests/commercial/test_samples.py`
- `backend/tests/commercial/test_sample_evaluations.py`
- `frontend/tests/components/sample-properties.test.tsx`
- `frontend/tests/components/sample-forms.test.tsx`
- `docs/modules/sample-properties.md`
