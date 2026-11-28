# Unified record history

`core/interfaces/record_history.py` is the strict write and visibility contract.
Each module registers its entity types, read permissions and organization/row
visibility rule. The foundation reader never imports business-module models.
Unknown, absent, foreign and unauthorized entities return the same 404.

`record_event` uses the existing strict activity provider within the mutation's
transaction. It never commits independently; failure rolls back the mutation.
Actor names come through `core/interfaces/user_directory`. Automatic events have
a null actor and their trigger in `related`.

Version-1 details:

```json
{
  "schema_version": 1,
  "changes": [
    {"field": "target_spec_json.color", "old": "blue", "new": "red"},
    {"field": "target_spec_json.thickness", "old": {"min": 0.7, "max": 0.75}, "new": {"min": 0.8, "max": 0.85}}
  ],
  "reason": "Correct specifications",
  "related": {"production_order_id": "<uuid>", "production_order_number": "PO-2026-000001"}
}
```

Decimals become strings, dates ISO strings, enums canonical codes. Each
specification key has a separate change; ranges remain `{min,max}`. Sensitive
password/token/secret/credential/recovery/authorization keys and change field
names are omitted recursively. Callers explicitly select business fields and
must never pass credentials in entity names or reasons.

## Reading, pagination and archives

`GET /record-history/{entity_type}/{entity_id}` uses ADR-006's page envelope,
default 50/max 100, newest first with ID as a deterministic tie breaker. Migration
`f6a1b2p9` adds its supporting index to the existing activity table.

`activity_archive` is a monthly export/download receipt, **not a database of
archived events**. CSV bytes are generated on request, returned and not retained.
Cleanup now preserves version-1 events and legacy events with an entity ID of a
registered history type. They remain in `foundation_activity_log`, are included
in exports, and the same organization-scoped query reads them after archival.
Completed months are excluded from repeated reminders/purges. Other activity
retains its previous retention policy. No new history/archive table is needed.

Events physically deleted before this change cannot be reconstructed from the
download receipt; previously downloaded CSV files are not imported. This is a
documented retention exception required to keep history queryable.

`RecordHistory` translates events, fields, template properties and enum values,
and formats specification ranges with `formatSpecValue`. Production orders keep
the previous `OrderStatusTimeline` in a collapsed "Previous status timeline"
section of the History tab, preserving older rows without duplicating them in
the main unified view. Existing status-history tables are not removed.

## Demand rework and immutable allocation sources

The organization mutex serializes edits, allocations, returns and status changes.
Header editing stays locked after the first allocation. Items may be edited in
draft/ready/partially-planned, or in planned when a free item exists. ACTIVE
allocations lock every item field (`DEMAND_ITEM_ALLOCATED`). Released history
permits editing, never deletion. Adding items is allowed in
draft/ready/partially-planned and synchronizes demand status. Existing sales-order
source restrictions and product/specification/unit validation remain.

Allocations copy `target_spec_json_snapshot`, `product_type_snapshot`, and the
existing immutable `unit`. Backfill uses demand items for active rows; released
rows prefer their linked order line and order product, otherwise the demand item.
Existing unit snapshots are retained. Only counts are logged. Downgrade removes
the two snapshot columns and history index; it does not modify source data.

The response additionally groups returned quantities by their allocation units;
the UI uses these exact decimal totals. Historical kilograms must never become
rolls just because a returned item now uses another unit. The older scalar total
remains in the API for compatibility, without interpreting it as one unit.

Return is blocked by rows in `production_result_entries`,
`production_waste_records`, `quality_checks`, `quality_defects`,
`quality_rejections`, or `quality_certificates`. Quality provides evidence through
`core/interfaces/order_line_evidence`; no cross-module model imports.
`production_allocations` is the other table with this exact item-ID column; its
rows represent planning provenance, not production. Runs and downtime reference
the order rather than an item and retain their order-level cancellation rules.
`LAST_ACTIVE_ALLOCATION` and `ORDER_ALLOCATION_LOCKED` are unchanged.

Actual results/quality also prevent line rebuilding on a released order; existing
lines are adjusted so returning an untouched sibling cannot erase another line's
execution history.

## Commercial (PR2)

`commercial/application/record_history.py` registers `customer`, `quote`,
`sample` and `sales_order`. Visibility is the record page's own RBAC-002 owner
filter (`visibility.visible_owner`): an "own" reader cannot read the history of
another sales owner's customer or of its quotations, samples and orders.

| Record | Events |
|---|---|
| `customer` | `customer.created/updated/owner_reassigned`, `customer.contact_added/updated`, `customer.site_added/updated`, `interaction.created/updated/deleted`, `followup.created/updated/completed/reopened/cancelled/reassigned/deleted`, and `quote.deleted`, `sample.deleted`, `sales_order.deleted` |
| `quote` | `quote.created/updated`, `quote.issued/accepted/rejected/expired/revised` (status and revision old→new, with the reason) |
| `sales_order` | `sales_order.created/updated` (`related.quote_number` when made from a quotation), `sales_order.confirmed/revised/cancelled` |
| `sample` | `sample.created/updated`, `sample.evaluation_added/updated/deleted` (with the sample status the evaluation changed) |

Child records (contacts, sites, interactions, follow-ups, evaluations) are
written under their parent with `related.subject_kind/subject_id/subject_name`,
so one tab shows them and a deleted child stays visible. A deleted quotation,
sample or draft order is written under its customer for the same reason.

Document lines are compared by line number. Each line change carries `line` and
`line_change` (`added`, `removed`, `changed`); specification keys are split as
above. People are stored by name (`sales_owner`, `assigned_user`, `contact`) and
linked records by number (`quote`, `sample`), never by id. Decimals are
normalized (`1000.000` and `1000` are one value), so re-reading a stored value
is not a change, and an edit that changes nothing writes nothing.

`core/contact_records.save` takes an optional `on_saved(before, row)` hook that
runs inside its transaction, before its commit.

Complaints keep their existing decision history (`commercial_complaint_events`,
COMPLAINTS-001). It already records every step with its actor, reason and named
facts, so it is not duplicated here. Quotations and sales orders also keep the
`commercial_status_history` timeline ("سجل الحالة"), which holds the steps
taken before this change.

Earlier `interaction.*` and `followup.*` activity rows were written with entity
types `interaction`/`followup`. They stay in the activity log but are not shown
in the customer's tab. Earlier `customer.*` rows have no version-1 details: the
tab shows their event without a change table.

The frontend `RecordHistory` is shared:
- shared words come from `common.recordHistory`;
- module words come from `<namespace>.events|fields|subjects`. The default is `production.recordHistory` for `production_*` records and `commercial.recordHistory` for the others.

Enumerations are worded by record (or child record) and field. Tabs marked
`lazy` build the history only while open, so it is read again on each visit.
