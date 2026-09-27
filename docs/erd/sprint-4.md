# ERD Notes — Sprint 4

5 new tables added across 5 Alembic migrations. All primary keys are UUIDs. Foundation, Sprint 1–3 tables: see [sprint-1.md](sprint-1.md), [sprint-2.md](sprint-2.md), [sprint-3.md](sprint-3.md).

**Module scaffold note (D10):** All 5 tables live in `backend/app/quality/`. NonConformanceReport and NonConformanceItem are co-located with Quality in v0.1 — not in a separate `ncr/` module.

---

## Quality tables (Sprint 4)

```
quality_checks
  id                        UUID PK
  organization_id           UUID FK → foundation_organizations   index
  inspection_code           VARCHAR(32)   NOT NULL               -- auto: QI-YYYY-NNNN (D3), never caller input
  check_datetime            TIMESTAMPTZ   NOT NULL
  check_type                ENUM(in_process_inspection, finished_product_inspection,
                                 sample_inspection, reinspection, issue_triggered, general)   NOT NULL   -- D4: business type
  status                    ENUM(open, under_inspection, closed)   NOT NULL   DEFAULT 'open'   -- lifecycle (D1)
  result                    ENUM(accepted, rejected, conditional_accept, needs_reinspection)   nullable  -- outcome (D1)
  qty_inspected             INTEGER       NOT NULL               -- gt=0; constraint: accepted + rejected = inspected (D2)
  qty_accepted              INTEGER       NOT NULL               -- ge=0
  qty_rejected              INTEGER       NOT NULL               -- ge=0
  production_order_id       UUID          nullable               -- plain ref, NO FK (ADR-004 boundary)
  production_order_item_id  UUID          nullable               -- plain ref, NO FK
  production_output_id      UUID          nullable               -- plain ref, NO FK
  shift_report_id           UUID          nullable               -- plain ref, NO FK
  notes                     TEXT          nullable
  checked_by_user_id        UUID FK → foundation_users           -- DB FK only — no model import
  created_at                TIMESTAMPTZ
  updated_at                TIMESTAMPTZ
  UNIQUE (organization_id, inspection_code)

quality_defects
  id                        UUID PK
  organization_id           UUID FK → foundation_organizations   -- direct tenant scope (dual isolation) (*)
  quality_check_id          UUID FK → quality_checks   index     -- required, NOT NULL (D5)
  production_order_id       UUID          nullable               -- plain ref
  production_order_item_id  UUID          nullable               -- plain ref
  production_output_id      UUID          nullable               -- plain ref
  defect_date               DATE          NOT NULL
  defect_category           ENUM(dimension, thickness, surface, color, strength, winding,
                                 weight, packaging, labeling, finish, other)   NOT NULL   -- 11 values (D7)
  severity                  ENUM(minor, major, critical)   NOT NULL
  defect_count              INTEGER       NOT NULL   DEFAULT 1   -- gt=0 (D6)
  description               TEXT          NOT NULL
  notes                     TEXT          nullable
  detected_by_user_id       UUID FK → foundation_users           -- DB FK only
  created_at                TIMESTAMPTZ
  updated_at                TIMESTAMPTZ
  -- (*) NO status field by design (D14) — static fact record

quality_rejections
  id                        UUID PK
  organization_id           UUID FK → foundation_organizations   index
  quality_check_id          UUID          nullable               -- plain ref (no FK); org validated in service
  quality_defect_id         UUID          nullable               -- plain ref; defect must belong to check if both set
  production_output_id      UUID          nullable               -- plain ref
  production_order_item_id  UUID          nullable               -- plain ref
  rejection_date            DATE          NOT NULL
  rejection_reason          ENUM(failed_quality_check, critical_defect, out_of_spec,
                                 dimension_failure, surface_failure, packaging_failure,
                                 labeling_issue, other)   NOT NULL
  rejection_notes           TEXT          NOT NULL               -- required, min_length=1 (D8 — Quality PRD BR-02)
  disposition               ENUM(hold, scrap, rework, return_to_process)   NOT NULL
  disposition_status        ENUM(pending, executed)   NOT NULL  -- auto-set to 'pending' on creation (D9)
  quantity_rejected         INTEGER       NOT NULL               -- gt=0
  unit                      VARCHAR(32)   NOT NULL
  rejected_by_user_id       UUID FK → foundation_users           -- DB FK only
  created_at                TIMESTAMPTZ
  updated_at                TIMESTAMPTZ

non_conformance_reports
  id                        UUID PK
  organization_id           UUID FK → foundation_organizations   index
  report_number             VARCHAR(32)   NOT NULL               -- auto: NCR-YYYY-NNNN (D11), never caller input
  report_date               DATE          NOT NULL
  source_type               ENUM(internal_production, incoming_material, supplier,
                                 warehouse, customer_return, other)   NOT NULL
  report_type               ENUM(material_non_conformance, product_non_conformance,
                                 process_non_conformance, packaging_non_conformance,
                                 documentation_non_conformance, other)   NOT NULL
  status                    ENUM(draft, open, under_review, closed)   NOT NULL   DEFAULT 'draft'   -- D11
  title                     VARCHAR(255)  NOT NULL               -- required, min_length=1
  description               TEXT          NOT NULL               -- required, min_length=1
  reference_code            VARCHAR(255)  nullable               -- optional batch/lot ref
  quality_check_id          UUID          nullable               -- plain ref, NO FK
  quality_rejection_id      UUID          nullable               -- plain ref, NO FK
  detected_by_user_id       UUID FK → foundation_users           -- DB FK only
  created_at                TIMESTAMPTZ
  updated_at                TIMESTAMPTZ
  UNIQUE (organization_id, report_number)

non_conformance_items
  id                              UUID PK
  non_conformance_report_id       UUID FK → non_conformance_reports   index   NOT NULL
  line_no                         INTEGER       NOT NULL               -- auto: (max+1) if not provided (D13)
  item_reference                  VARCHAR(255)  nullable               -- optional batch/PN
  item_name                       VARCHAR(255)  NOT NULL               -- required, min_length=1
  quantity_affected               NUMERIC(14,2) nullable               -- nullable (may be unknown at case open)
  unit                            VARCHAR(32)   nullable
  issue_description               TEXT          NOT NULL               -- required, min_length=1
  notes                           TEXT          nullable
  created_at                      TIMESTAMPTZ
  updated_at                      TIMESTAMPTZ
  UNIQUE (non_conformance_report_id, line_no)
  -- NO organization_id: tenant isolation cascaded via parent NonConformanceReport JOIN (*)
  -- NO status field by design (D14) — parent report status governs item lifecycle
```

---

## Tenant isolation notes

```
quality_defects.organization_id
  → Direct column (NOT cascaded). QualityDefect has BOTH direct org AND parent JOIN check.
  → This is dual-isolation — more secure than strictly required by ADR-001.
  → get_by_id filters by BOTH QualityDefect.organization_id AND QualityCheck.organization_id.

non_conformance_items
  → NO organization_id column (cascaded only).
  → get_by_id JOINs non_conformance_reports and filters by NonConformanceReport.organization_id.
  → list_by_report does NOT re-filter by org (safe — service validates parent first).
```

---

## Relationships summary (Sprint 4 additions)

```
foundation_organizations         1──* quality_checks
foundation_organizations         1──* quality_defects              (direct org column)
foundation_organizations         1──* quality_rejections
foundation_organizations         1──* non_conformance_reports

quality_checks                   1──* quality_defects              (FK, NOT NULL — required)

non_conformance_reports          1──* non_conformance_items        (cascade delete)

-- Plain UUID cross-references (NO FK constraints — module boundary ADR-004):
quality_checks          ──(uuid)──  production_orders
quality_checks          ──(uuid)──  production_outputs
quality_checks          ──(uuid)──  production_shift_reports
quality_rejections      ──(uuid)──  quality_checks                 (optional ref)
quality_rejections      ──(uuid)──  quality_defects                (optional ref)
non_conformance_reports ──(uuid)──  quality_checks                 (optional ref)
non_conformance_reports ──(uuid)──  quality_rejections             (optional ref)

-- DB-level FK only (no model import):
foundation_users        ──(fk)──    quality_checks.checked_by_user_id
foundation_users        ──(fk)──    quality_defects.detected_by_user_id
foundation_users        ──(fk)──    quality_rejections.rejected_by_user_id
foundation_users        ──(fk)──    non_conformance_reports.detected_by_user_id
```

---

## Migration chain (Sprint 4 additions)

| Migration | Description |
|-----------|-------------|
| `a1b2c3d4` | `quality_checks` |
| `b2c3d4e5` | `quality_defects` |
| `c3d4e5f6` | `quality_rejections` |
| `d4e5f6a7` | `non_conformance_reports` |
| `e5f6a7b8` ← HEAD | `non_conformance_items` |

Run `alembic upgrade head` from `backend/` to apply all migrations.
