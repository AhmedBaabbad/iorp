"""Seed one organization, two users, roles, permissions, and full Sprint 1-4
development data for local development.

Sprint 1: Foundation + Commercial CRM baseline (customers, interactions, follow-ups)
Sprint 2: Commercial Slice 2 (samples, evaluations, quotes, orders)
Sprint 3: Production baseline (work centers, shifts, orders, outputs, downtime, waste)
Sprint 4: Quality & NCR baseline (quality checks, defects, rejections, NCR reports, items)

Skips if the dev-org already exists — drop and re-create the database to re-seed.
To reset: bash scripts/reset-db.sh  (drops the DB)
          alembic upgrade head       (re-applies all migrations)
          python scripts/seed-dev-data.py
"""

import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.db import SessionLocal
from app.core.permission_catalog import PERMISSIONS
from app.core.security import hash_password
from app.commercial.domain.enums import (
    CommercialOrderStatus,
    CustomerStatus,
    FollowUpStatus,
    InteractionType,
    PriorityLevel,
    QuoteStatus,
    RelationshipStage,
    SampleEvaluationNextAction,
    SampleEvaluationResultStatus,
    SampleStatus,
)
from app.commercial.infrastructure.models import (
    CommercialOrder,
    CommercialOrderItem,
    Customer,
    CustomerInteraction,
    FollowUp,
    Quote,
    QuoteItem,
    Sample,
    SampleEvaluation,
)
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import (
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.production.domain.enums import (
    DowntimeCategory,
    DowntimeStatus,
    ProductionOrderPriority,
    ProductionOrderStatus,
    ProductionOutputStatus,
    ShiftDefinitionStatus,
    ShiftReportStatus,
    ShiftType,
    WasteCategory,
    WorkCenterStatus,
    WorkCenterType,
)
from app.production.infrastructure.models import (
    DowntimeEvent,
    ProductionOrder,
    ProductionOrderItem,
    ProductionOutput,
    ShiftDefinition,
    ShiftReport,
    WasteRecord,
    WorkCenter,
)
from app.quality.domain.enums import (
    DefectCategory,
    DefectSeverity,
    Disposition,
    DispositionStatus,
    NCRReportType,
    NCRSourceType,
    NCRStatus,
    QualityCheckStatus,
    QualityCheckType,
    RejectionReason,
)
from app.quality.infrastructure.models import (
    NonConformanceItem,
    NonConformanceReport,
    QualityCheck,
    QualityDefect,
    QualityRejection,
)


# ── Seed constants ─────────────────────────────────────────────────────────────

ORG_CODE = "dev-org"

# PERMISSIONS is the canonical catalog, shared with BootstrapService — see
# app/core/permission_catalog.py.

COMMERCIAL_PERMISSION_CODES = {
    p["code"] for p in PERMISSIONS if p["module_name"] == "commercial"
}

ORG_ADMIN_PERMISSION_CODES = {
    p["code"]
    for p in PERMISSIONS
    if p["module_name"] in ("foundation", "workforce") or p["code"].endswith(":read")
} | {
    "commercial:customers:assign_owner",
    "commercial:follow_ups:assign",
    "commercial:follow_ups:complete",
}

COMMERCIAL_MANAGER_PERMISSION_CODES = {
    f"commercial:{resource}:{action}"
    for resource in ("customers", "interactions", "follow_ups", "samples", "evaluations", "quotes", "orders")
    for action in ("read", "create", "update")
} | {
    "commercial:interactions:delete",
    "commercial:follow_ups:delete",
    "commercial:customers:assign_owner",
    "commercial:follow_ups:assign",
    "commercial:follow_ups:complete",
}

PRODUCTION_MANAGER_PERMISSION_CODES = {
    p["code"] for p in PERMISSIONS if p["module_name"] == "production"
} | {"workforce:members:read", "workforce:members:update"}

QUALITY_MANAGER_PERMISSION_CODES = {
    p["code"] for p in PERMISSIONS if p["module_name"] == "quality"
}

PRODUCTION_SUPERVISOR_PERMISSION_CODES = {
    "production:shift_reports:read",
    "production:shift_reports:write",
    "production:production_orders:read",
    "production:downtime_events:read",
    "production:downtime_events:write",
    "production:waste_records:read",
    "production:waste_records:write",
}

SALES_REP_PERMISSION_CODES = {
    "commercial:customers:read",
    "commercial:customers:create",
    "commercial:customers:update",
    "commercial:interactions:read",
    "commercial:interactions:create",
    "commercial:interactions:update",
    "commercial:follow_ups:read",
    "commercial:follow_ups:create",
    "commercial:follow_ups:update",
    "commercial:follow_ups:complete",
    "commercial:samples:read",
    "commercial:samples:create",
    "commercial:quotes:read",
    "commercial:quotes:create",
    "commercial:orders:read",
}

SALES_ASSISTANT_PERMISSION_CODES = {
    "commercial:customers:read",
    "commercial:interactions:read", "commercial:interactions:create",
    "commercial:follow_ups:read", "commercial:follow_ups:create",
    "commercial:follow_ups:update", "commercial:follow_ups:complete",
    "commercial:samples:read",
    "commercial:quotes:read",
    "commercial:orders:read",
}

QUALITY_INSPECTOR_PERMISSION_CODES = {
    "quality:quality_checks:read",
    "quality:quality_checks:write",
    "quality:quality_defects:read",
    "quality:quality_defects:write",
    "quality:rejections:read",
    "quality:ncr_reports:read",
}

ROLES = [
    dict(name="Admin", code="admin", description="Full access to all modules."),
    dict(name="Super Admin", code="super_admin", description="Full access to all modules."),
    dict(name="Organization Admin", code="org_admin", description="Foundation administration and read access across modules."),
    dict(name="Commercial Manager", code="commercial_manager", description="Commercial module management access."),
    dict(name="Production Manager", code="production_manager", description="Production module management access."),
    dict(name="Quality Manager", code="quality_manager", description="Quality module management access."),
    dict(name="Production Supervisor", code="production_supervisor", description="Production floor supervision access."),
    dict(name="Sales Rep", code="sales_rep", description="Commercial sales access."),
    dict(name="Sales Assistant", code="sales_assistant", description="Commercial support access."),
    dict(name="Quality Inspector", code="quality_inspector", description="Quality inspection access."),
]

USERS = [
    dict(full_name="Dev Admin",           email="admin@iorp-dev.com",    password="Admin1234!",   role_code="admin"),
    dict(full_name="Org Admin",           email="org-admin@iorp-dev.com", password="OrgAdmin1!",  role_code="org_admin"),
    dict(full_name="Commercial Manager",  email="comm-mgr@iorp-dev.com", password="CommMgr1!",   role_code="commercial_manager"),
    dict(full_name="Production Manager",  email="prod-mgr@iorp-dev.com", password="ProdMgr1!",   role_code="production_manager"),
    dict(full_name="Quality Manager",     email="qual-mgr@iorp-dev.com", password="QualMgr1!",   role_code="quality_manager"),
    dict(full_name="Production Supervisor", email="prod-sup@iorp-dev.com", password="ProdSup1!", role_code="production_supervisor"),
    dict(full_name="Quality Inspector",   email="qc-insp@iorp-dev.com",  password="QcInsp01!",   role_code="quality_inspector"),
    dict(full_name="Sales Rep",           email="sales@iorp-dev.com",    password="Sales1234!",   role_code="sales_rep"),
]

CUSTOMERS = [
    dict(customer_code="CUST-001", name="TechCorp Industries",     sector="Technology",   city="Dubai",     country="UAE", relationship_stage=RelationshipStage.LEAD,     priority_level=PriorityLevel.HIGH,   notes="Warm lead from referral."),
    dict(customer_code="CUST-002", name="BuildCo Contracting",     sector="Construction", city="Abu Dhabi", country="UAE", relationship_stage=RelationshipStage.ACTIVE_CUSTOMER, priority_level=PriorityLevel.MEDIUM, notes="Submitted a quote in May."),
    dict(customer_code="CUST-003", name="RetailPlus Distribution", sector="Retail",       city="Sharjah",   country="UAE", relationship_stage=RelationshipStage.ACTIVE_CUSTOMER, priority_level=PriorityLevel.LOW,    notes="Existing account, low activity."),
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_or_create_permission(db, perm: dict) -> Permission:
    existing = db.query(Permission).filter_by(code=perm["code"]).first()
    if existing:
        return existing
    obj = Permission(**perm)
    db.add(obj)
    db.flush()
    return obj


def _get_or_create_role(db, org_id, role: dict) -> Role:
    existing = db.query(Role).filter_by(organization_id=org_id, code=role["code"]).first()
    if existing:
        return existing
    obj = Role(organization_id=org_id, **role)
    db.add(obj)
    db.flush()
    return obj


def _assign_permission(db, role_id, permission_id) -> None:
    existing = db.query(RolePermission).filter_by(role_id=role_id, permission_id=permission_id).first()
    if not existing:
        db.add(RolePermission(role_id=role_id, permission_id=permission_id))


def _get_or_create_user(db, org_id, user: dict, role_id) -> User:
    existing = db.query(User).filter_by(organization_id=org_id, email=user["email"]).first()
    if existing:
        return existing
    obj = User(
        organization_id=org_id,
        full_name=user["full_name"],
        email=user["email"],
        password_hash=hash_password(user["password"]),
        status=UserStatus.ACTIVE,
    )
    db.add(obj)
    db.flush()
    assign = db.query(UserRole).filter_by(user_id=obj.id, role_id=role_id).first()
    if not assign:
        db.add(UserRole(user_id=obj.id, role_id=role_id))
    return obj


# ── Main seed ──────────────────────────────────────────────────────────────────

def seed() -> None:
    db = SessionLocal()
    try:
        existing_org = db.query(Organization).filter_by(code=ORG_CODE).first()
        if existing_org:
            print("Seed data already exists — skipping.")
            print(f"  org_id  : {existing_org.id}")
            print("  To re-seed: drop the database and run 'alembic upgrade head' first.")
            return

        # ── Foundation ────────────────────────────────────────────────────────

        org = Organization(
            name="Dev Organization",
            code=ORG_CODE,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
        )
        db.add(org)
        db.flush()

        perms = {p["code"]: _get_or_create_permission(db, p) for p in PERMISSIONS}

        roles = {r["code"]: _get_or_create_role(db, org.id, r) for r in ROLES}

        role_permission_codes = {
            "admin": set(perms.keys()),
            "super_admin": set(perms.keys()),
            "org_admin": ORG_ADMIN_PERMISSION_CODES,
            "commercial_manager": COMMERCIAL_MANAGER_PERMISSION_CODES,
            "production_manager": PRODUCTION_MANAGER_PERMISSION_CODES,
            "quality_manager": QUALITY_MANAGER_PERMISSION_CODES,
            "production_supervisor": PRODUCTION_SUPERVISOR_PERMISSION_CODES,
            "sales_rep": SALES_REP_PERMISSION_CODES,
            "sales_assistant": SALES_ASSISTANT_PERMISSION_CODES,
            "quality_inspector": QUALITY_INSPECTOR_PERMISSION_CODES,
        }

        for perm_code, perm_obj in perms.items():
            for role_code, granted_codes in role_permission_codes.items():
                if perm_code in granted_codes:
                    _assign_permission(db, roles[role_code].id, perm_obj.id)

        users = {}
        for u in USERS:
            role = roles[u["role_code"]]
            users[u["email"]] = _get_or_create_user(db, org.id, u, role.id)

        admin_user = users["admin@iorp-dev.com"]

        # ── Commercial Sprint 1: Customers, interactions, follow-ups ──────────

        customers = []
        for c in CUSTOMERS:
            obj = Customer(
                organization_id=org.id,
                status=CustomerStatus.ACTIVE,
                created_by_user_id=admin_user.id,
                **c,
            )
            db.add(obj)
            customers.append(obj)
        db.flush()

        interaction = CustomerInteraction(
            customer_id=customers[0].id,
            interaction_type=InteractionType.CALL,
            interaction_date=datetime.now(timezone.utc) - timedelta(days=3),
            subject="Initial discovery call",
            summary="Discussed current infrastructure needs and timeline.",
            outcome="Positive — requested a formal proposal.",
            next_step_hint="Send proposal by end of week.",
            created_by_user_id=admin_user.id,
        )
        db.add(interaction)
        db.flush()

        follow_up = FollowUp(
            customer_id=customers[0].id,
            interaction_id=interaction.id,
            assigned_user_id=admin_user.id,
            due_date=datetime.now(timezone.utc) + timedelta(days=4),
            priority=PriorityLevel.HIGH,
            status=FollowUpStatus.PENDING,
            reason="Send proposal document",
            notes="Include pricing for the enterprise tier.",
        )
        db.add(follow_up)
        db.flush()

        # ── Commercial Sprint 2: Sample → Evaluation → Quote → Order ─────────

        sample = Sample(
            customer_id=customers[1].id,
            sample_code="SAMP-001",
            product_type="Steel Rod",
            requested_spec_json={"grade": "S235", "diameter_mm": 12},
            quantity_requested=Decimal("500.00"),
            unit="kg",
            request_date=datetime.now(timezone.utc) - timedelta(days=7),
            status=SampleStatus.EVALUATED,
            notes="Customer requested for structural trial.",
            created_by_user_id=admin_user.id,
        )
        db.add(sample)
        db.flush()

        evaluation = SampleEvaluation(
            sample_id=sample.id,
            evaluation_date=datetime.now(timezone.utc) - timedelta(days=3),
            result_status=SampleEvaluationResultStatus.ACCEPTED,
            comments="Meets structural grade requirements. Customer approved.",
            next_action=SampleEvaluationNextAction.PROCEED_TO_QUOTE,
            evaluated_by_user_id=admin_user.id,
        )
        db.add(evaluation)
        db.flush()

        _subtotal = Decimal("3010.00")
        _discount = Decimal("60.00")
        _tax      = Decimal("0.00")
        _total    = _subtotal - _discount + _tax
        quote = Quote(
            organization_id=org.id,
            customer_id=customers[1].id,
            sample_id=sample.id,
            quote_number="Q-2026-001",
            issue_date=datetime.now(timezone.utc) - timedelta(days=2),
            valid_until=datetime.now(timezone.utc) + timedelta(days=28),
            status=QuoteStatus.ISSUED,
            currency="SAR",
            subtotal_amount=_subtotal,
            discount_amount=_discount,
            tax_amount=_tax,
            total_amount=_total,
            notes="Based on approved sample SAMP-001.",
            created_by_user_id=admin_user.id,
            items=[
                QuoteItem(line_no=1, product_type="Steel Rod", quantity=Decimal("500.00"), unit="kg", unit_price=Decimal("4.50"), line_total=Decimal("2250.00")),
                QuoteItem(line_no=2, product_type="Rebar",     quantity=Decimal("200.00"), unit="kg", unit_price=Decimal("3.80"), line_total=Decimal("760.00")),
            ],
        )
        db.add(quote)
        db.flush()

        commercial_order = CommercialOrder(
            organization_id=org.id,
            customer_id=customers[1].id,
            quote_id=quote.id,
            order_number="ORD-2026-001",
            order_date=datetime.now(timezone.utc) - timedelta(days=1),
            status=CommercialOrderStatus.CONFIRMED,
            requested_delivery_date=datetime.now(timezone.utc) + timedelta(days=14),
            notes="Confirmed based on Q-2026-001.",
            created_by_user_id=admin_user.id,
            items=[
                CommercialOrderItem(line_no=1, product_type="Steel Rod", quantity=Decimal("500.00"), unit="kg", agreed_unit_price=Decimal("4.50"), line_total=Decimal("2250.00")),
                CommercialOrderItem(line_no=2, product_type="Rebar",     quantity=Decimal("200.00"), unit="kg", agreed_unit_price=Decimal("3.80"), line_total=Decimal("760.00")),
            ],
        )
        db.add(commercial_order)
        db.flush()

        # ── Production Sprint 3 ────────────────────────────────────────────────
        # The production seed covers the full operational chain:
        # work centers → shift definitions → production orders → items →
        # shift report → production output + downtime events + waste record

        # Work centers (two lines: extrusion and packing)
        wc_extrusion = WorkCenter(
            organization_id=org.id,
            code="WC-001",
            name="Extrusion Line 1",
            center_type=WorkCenterType.EXTRUSION,
            status=WorkCenterStatus.ACTIVE,
            location="Hall A",
            notes="Primary extrusion line. PE/PP compound runs.",
        )
        wc_packing = WorkCenter(
            organization_id=org.id,
            code="WC-002",
            name="Packing Unit 1",
            center_type=WorkCenterType.PACKING,
            status=WorkCenterStatus.ACTIVE,
            location="Hall B",
        )
        db.add(wc_extrusion)
        db.add(wc_packing)
        db.flush()

        # Shift definitions — three shifts covering all schedule scenarios.
        # NOTE: crosses_midnight and duration_hours are computed here directly
        # because seed bypasses the service layer. The service uses the same formula:
        #   crosses_midnight = end_time <= start_time
        #   duration = (end - start) mod 24h → hours
        shift_morn = ShiftDefinition(
            organization_id=org.id,
            code="SHIFT-MORN",
            name="Morning Shift",
            shift_type=ShiftType.MORNING,
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=Decimal("8.00"),
            crosses_midnight=False,   # 15:00 > 07:00 → does not cross midnight
            status=ShiftDefinitionStatus.ACTIVE,
        )
        shift_eve = ShiftDefinition(
            organization_id=org.id,
            code="SHIFT-EVE",
            name="Evening Shift",
            shift_type=ShiftType.EVENING,
            start_time=time(15, 0),
            end_time=time(23, 0),
            duration_hours=Decimal("8.00"),
            crosses_midnight=False,   # 23:00 > 15:00 → does not cross midnight
            status=ShiftDefinitionStatus.ACTIVE,
        )
        # CRITICAL EDGE CASE: night shift crosses midnight.
        # end_time(07:00) <= start_time(23:00) → crosses_midnight = True
        # This is the primary test case for D5 (crosses_midnight auto-calculation).
        shift_night = ShiftDefinition(
            organization_id=org.id,
            code="SHIFT-NIGHT",
            name="Night Shift",
            shift_type=ShiftType.NIGHT,
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=Decimal("8.00"),
            crosses_midnight=True,    # 07:00 <= 23:00 → crosses midnight (D5)
            status=ShiftDefinitionStatus.ACTIVE,
        )
        db.add(shift_morn)
        db.add(shift_eve)
        db.add(shift_night)
        db.flush()

        today = date.today()

        # Production orders.
        po_001 = ProductionOrder(
            organization_id=org.id,
            production_order_number="PO-001",
            work_center_id=wc_extrusion.id,
            product_type="Steel Rod 14mm",
            target_spec_json={"grade": "S235", "diameter_mm": 14, "length_m": 6},
            planned_quantity=Decimal("5000.00"),
            unit="kg",
            priority=ProductionOrderPriority.URGENT,
            status=ProductionOrderStatus.IN_PROGRESS,
            planned_start_date=today,
            planned_end_date=today + timedelta(days=5),
            notes="Convert from ORD-2026-001. First priority run.",
            created_by_user_id=admin_user.id,
        )
        # PO-002 is a draft order with default priority (demonstrates D8: priority defaults to normal)
        po_002 = ProductionOrder(
            organization_id=org.id,
            production_order_number="PO-002",
            work_center_id=wc_packing.id,
            product_type="Rebar 10mm",
            target_spec_json={"grade": "B500B", "diameter_mm": 10},
            planned_quantity=Decimal("2000.00"),
            unit="kg",
            priority=ProductionOrderPriority.NORMAL,  # default priority (D8)
            status=ProductionOrderStatus.DRAFT,
            planned_start_date=today + timedelta(days=7),
            planned_end_date=today + timedelta(days=12),
            created_by_user_id=admin_user.id,
        )
        db.add(po_001)
        db.add(po_002)
        db.flush()

        # Production order items for PO-001.
        # line_no is provided explicitly here (seed bypasses service auto-assignment).
        # In API usage, line_no auto-assigns as max(existing) + 1 when not provided.
        item_1 = ProductionOrderItem(
            production_order_id=po_001.id,
            line_no=1,
            target_spec_json={"width_mm": 500, "thickness_mm": 0.8},
            planned_quantity=Decimal("3000.00"),
            unit="kg",
            notes="Wide roll — primary customer spec.",
        )
        item_2 = ProductionOrderItem(
            production_order_id=po_001.id,
            line_no=2,
            target_spec_json={"width_mm": 300, "thickness_mm": 1.2},
            planned_quantity=Decimal("2000.00"),
            unit="kg",
            notes="Narrow roll — secondary spec.",
        )
        db.add(item_1)
        db.add(item_2)
        db.flush()

        # Shift report for the morning shift on PO-001.
        # shift_definition_id used (not shift_id — D1).
        # status = submitted means shift has ended and is pending approval.
        shift_started = datetime(today.year, today.month, today.day, 7, 0, 0, tzinfo=timezone.utc)
        shift_ended   = datetime(today.year, today.month, today.day, 15, 0, 0, tzinfo=timezone.utc)
        shift_report = ShiftReport(
            organization_id=org.id,
            work_center_id=wc_extrusion.id,
            shift_definition_id=shift_morn.id,   # shift_definition_id — correct FK name (D1)
            production_order_id=po_001.id,
            report_date=today,
            shift_started_at=shift_started,
            shift_ended_at=shift_ended,
            status=ShiftReportStatus.SUBMITTED,
            summary=(
                "Morning shift — Steel Rod 14mm on PO-001. "
                "850 kg produced. 25 kg startup loss. "
                "One machine downtime (hydraulic, 45 min). Shift closed normally."
            ),
            notes="Operator: Ahmed. QC sample taken at 10:00.",
            created_by_user_id=admin_user.id,
        )
        db.add(shift_report)
        db.flush()

        # Production output for PO-001 on this shift.
        # work_center_id is required at output level (D2) — may differ from order's planned work center.
        production_output = ProductionOutput(
            organization_id=org.id,
            production_order_id=po_001.id,
            work_center_id=wc_extrusion.id,    # required (D2) — actual production work center
            shift_report_id=shift_report.id,
            production_order_item_id=item_1.id, # output is against line 1 (wide roll)
            output_date=today,
            recorded_at=shift_started + timedelta(hours=4),  # recorded mid-shift
            quantity_produced=Decimal("850.00"),
            unit="kg",
            output_status=ProductionOutputStatus.RECORDED,
            notes="First 4h of morning run. Wide roll only.",
            created_by_user_id=admin_user.id,
        )
        db.add(production_output)
        db.flush()

        # Downtime events — two events to cover OPEN and CLOSED scenarios.
        # status and duration_minutes are computed here to mirror service layer logic:
        #   _derive_status: end_time is None → OPEN
        #   _calculate_duration_minutes: int((end - start).total_seconds() // 60)

        # DT-001: OPEN downtime — still in progress, no end_time
        # Demonstrates D3 (duration_minutes = NULL) and D4 (status = 'open')
        dt_001_start = datetime(today.year, today.month, today.day, 13, 30, 0, tzinfo=timezone.utc)
        downtime_open = DowntimeEvent(
            organization_id=org.id,
            work_center_id=wc_extrusion.id,    # required (D2)
            shift_report_id=shift_report.id,
            production_order_id=po_001.id,
            start_time=dt_001_start,
            end_time=None,                      # no end_time → status = OPEN (D4)
            duration_minutes=None,              # NULL because end_time is None (D3)
            category=DowntimeCategory.MACHINE,
            reason_code="Hydraulic pump pressure drop on extruder motor",  # free-text (D6)
            status=DowntimeStatus.OPEN,         # auto-derived: end_time is None → OPEN (D4)
            created_by_user_id=admin_user.id,
        )

        # DT-002: CLOSED downtime — 45-minute setup stop, now resolved
        # Demonstrates D3 (duration_minutes = 45, auto-calculated) and D4 (status = 'closed')
        dt_002_start = datetime(today.year, today.month, today.day, 9, 0, 0, tzinfo=timezone.utc)
        dt_002_end   = datetime(today.year, today.month, today.day, 9, 45, 0, tzinfo=timezone.utc)
        downtime_closed = DowntimeEvent(
            organization_id=org.id,
            work_center_id=wc_extrusion.id,    # required (D2)
            shift_report_id=shift_report.id,
            production_order_id=po_001.id,
            start_time=dt_002_start,
            end_time=dt_002_end,
            duration_minutes=45,               # int((dt_002_end - dt_002_start).total_seconds() // 60) = 45 (D3)
            category=DowntimeCategory.SETUP,
            reason_code="Die head cleaning during product changeover",  # free-text (D6)
            status=DowntimeStatus.CLOSED,      # auto-derived: end_time is set → CLOSED (D4)
            created_by_user_id=admin_user.id,
        )
        db.add(downtime_open)
        db.add(downtime_closed)
        db.flush()

        # Waste record for PO-001 — startup loss at beginning of shift.
        # WasteRecord has no status field (D7 — intentional for v0.1).
        # reason_code is free-text string — no enum or lookup table (D6).
        # work_center_id is required (D2).
        waste_record = WasteRecord(
            organization_id=org.id,
            production_order_id=po_001.id,
            work_center_id=wc_extrusion.id,    # required (D2)
            shift_report_id=shift_report.id,
            production_order_item_id=None,     # waste not tied to a specific line item
            waste_date=today,
            quantity_wasted=Decimal("25.00"),
            unit="kg",
            waste_category=WasteCategory.STARTUP_LOSS,
            reason_code="Film tear during startup on motor 3",  # free-text (D6) — no status (D7)
            notes="First 15 minutes of run. Resolved after tension adjustment.",
            created_by_user_id=admin_user.id,
        )
        db.add(waste_record)
        db.flush()

        # ── Quality Chain (Sprint 4) ───────────────────────────────────────────
        # Demonstrates Sprint 4 design decisions D1-D9.
        # NOTE: This section bypasses the service layer and creates models directly,
        # mirroring exactly what each service method would compute and set.

        # Step 1 — QualityCheck (D1, D2, D3, D4)
        # D3: inspection_code is auto-generated by the service as QI-YYYY-NNNN.
        #     Here we set it directly (seed bypasses service), using the same pattern.
        # D4: check_type must be a BUSINESS TYPE — not a measurement method.
        #     CORRECT: in_process_inspection / finished_product_inspection / etc.
        #     WRONG:   visual / dimension / tensile / weight (those are measurement methods)
        # D2: qty constraint — qty_accepted + qty_rejected MUST equal qty_inspected.
        #     Here: 85 + 15 = 100 ✓
        # D1: status and result are TWO SEPARATE fields.
        #     status = lifecycle (auto-set to OPEN on creation)
        #     result = outcome (null until the inspection concludes)
        quality_check = QualityCheck(
            organization_id=org.id,
            inspection_code="QI-2026-0001",         # D3: QI-YYYY-NNNN format (service auto-generates this)
            check_datetime=datetime(today.year, today.month, today.day, 10, 0, 0, tzinfo=timezone.utc),
            check_type=QualityCheckType.IN_PROCESS_INSPECTION,  # D4: business type
            status=QualityCheckStatus.OPEN,          # D1: lifecycle — always OPEN on creation
            result=None,                             # D1: outcome — null on creation
            qty_inspected=100,                       # D2: total units submitted
            qty_accepted=85,                         # D2: passed
            qty_rejected=15,                         # D2: failed | 85+15=100 ✓ constraint satisfied
            production_order_id=po_001.id,           # plain UUID ref — no FK (ADR-004)
            notes="Extrusion line 1 — film thickness spot check at hour 2.",
            checked_by_user_id=admin_user.id,
        )
        db.add(quality_check)
        db.flush()

        # Step 2 — QualityDefect (D5, D6, D7)
        # D5: quality_check_id is REQUIRED — links to the check created in Step 1.
        #     In API usage, check_id comes from the URL path:
        #     POST /quality-checks/{check_id}/defects
        # D6: defect_count = 15. Default is 1. Must be > 0.
        # D7: defect_category must be one of 11 approved values.
        #     APPROVED: dimension / thickness / surface / color / strength /
        #               winding / weight / packaging / labeling / finish / other
        quality_defect = QualityDefect(
            organization_id=org.id,
            quality_check_id=quality_check.id,       # D5: required — linked to Step 1 check
            defect_date=today,
            defect_category=DefectCategory.THICKNESS, # D7: one of 11 approved categories
            severity=DefectSeverity.MAJOR,
            defect_count=15,                          # D6: number of units with this defect
            description="Film thickness deviation on line 1: measured 0.3mm, target 0.5mm.",
            notes="Consistent across the roll — not isolated to one edge.",
            detected_by_user_id=admin_user.id,
        )
        db.add(quality_defect)
        db.flush()

        # Step 3 — QualityRejection (D8, D9)
        # D8: rejection_notes is REQUIRED (Quality PRD BR-02).
        #     Field(min_length=1) in schema + whitespace guard in service.
        #     Always include meaningful rejection notes — empty or whitespace → error.
        # D9: disposition_status is AUTO-SET to PENDING on creation.
        #     Do NOT provide it in the create body — the service sets it.
        #     Here we set it directly (seed bypasses service).
        quality_rejection = QualityRejection(
            organization_id=org.id,
            quality_check_id=quality_check.id,       # links to Step 1 check
            quality_defect_id=quality_defect.id,     # links to Step 2 defect (same check — D*coherence)
            rejection_date=today,
            rejection_reason=RejectionReason.DIMENSION_FAILURE,
            rejection_notes=(                         # D8: required — non-empty, meaningful text
                "Batch rejected: consistent film thickness deviation exceeding tolerance threshold. "
                "Measured 0.3mm across all samples; target is 0.5mm ±0.05mm."
            ),
            disposition=Disposition.REWORK,
            disposition_status=DispositionStatus.PENDING,  # D9: auto-set to PENDING (service does this)
            quantity_rejected=15,
            unit="rolls",
            rejected_by_user_id=admin_user.id,
        )
        db.add(quality_rejection)
        db.flush()

        # Step 4 — Update disposition_status to EXECUTED (D9)
        # Demonstrates the pending → executed transition.
        # In API usage: PATCH /quality-rejections/{id} {"disposition_status": "executed"}
        quality_rejection.disposition_status = DispositionStatus.EXECUTED
        db.flush()

        # ── NCR Chain (Sprint 4) ───────────────────────────────────────────────
        # Demonstrates Sprint 4 design decisions D10–D14.
        # NOTE: NCR lives in backend/app/quality/ — NOT a separate ncr/ module (D10).

        # Step 5 — NonConformanceReport (D10, D11)
        # D11: report_number is AUTO-GENERATED as NCR-YYYY-NNNN.
        #      Do NOT provide it in the create body (service generates it).
        #      Here we set it directly (seed bypasses service).
        # D11: status is AUTO-SET to DRAFT on creation.
        #      Do NOT provide status in the create body.
        # D10: This model lives in backend/app/quality/ — co-located with Quality.
        ncr_report = NonConformanceReport(
            organization_id=org.id,
            report_number="NCR-2026-0001",           # D11: NCR-YYYY-NNNN (service auto-generates this)
            report_date=today,
            source_type=NCRSourceType.INCOMING_MATERIAL,
            report_type=NCRReportType.MATERIAL_NON_CONFORMANCE,
            status=NCRStatus.DRAFT,                  # D11: always DRAFT on creation (service sets this)
            title="Non-conforming LLDPE granules — Batch B-44",
            description=(
                "Received LLDPE granules batch B-44 with moisture content exceeding specification. "
                "Visual inspection shows yellowish tint on Grade B material."
            ),
            reference_code="BATCH-B-44",
            quality_check_id=quality_check.id,       # optional plain UUID ref to Step 1 check
            quality_rejection_id=None,               # no rejection reference on this NCR
            detected_by_user_id=admin_user.id,
        )
        db.add(ncr_report)
        db.flush()

        # Step 6 — Update NCR status: draft → open → under_review
        # Demonstrates the status lifecycle.
        # In API usage: PATCH /non-conformance-reports/{id} {"status": "open"}
        ncr_report.status = NCRStatus.OPEN
        db.flush()
        ncr_report.status = NCRStatus.UNDER_REVIEW
        db.flush()

        # Step 7 — NCR Item 1 (D13, D14)
        # D13: line_no is AUTO-ASSIGNED as (max_line_no or 0) + 1 if not provided.
        #      In API usage: omit line_no to get auto-assignment.
        #      Here we set it explicitly (seed bypasses service).
        # D14: NonConformanceItem has NO status field by design.
        #      It is a static line item — parent report status governs item lifecycle.
        ncr_item_1 = NonConformanceItem(
            non_conformance_report_id=ncr_report.id,
            line_no=1,                                # D13: auto-assigned in API (max+1); set here for seed
            item_reference="BATCH-B-44-GRD-A",
            item_name="LLDPE Granules — Grade A",
            quantity_affected=Decimal("500.00"),
            unit="kg",
            issue_description=(
                "Moisture content measured at 0.12%, specification maximum is 0.05%. "
                "All 500 kg of Grade A material in batch B-44 affected."
            ),
            notes="Pending supplier analysis report.",
        )
        db.add(ncr_item_1)
        db.flush()

        # Step 8 — NCR Item 2 (D13)
        # D13: line_no auto-increments — this item is line 2.
        ncr_item_2 = NonConformanceItem(
            non_conformance_report_id=ncr_report.id,
            line_no=2,                                # D13: next line in sequence
            item_reference="BATCH-B-44-GRD-B",
            item_name="LLDPE Granules — Grade B",
            quantity_affected=Decimal("250.00"),
            unit="kg",
            issue_description=(
                "Color deviation: yellowish tint observed across all Grade B samples. "
                "Suspected contamination during transport."
            ),
            notes="Visual inspection only — lab analysis pending.",
        )
        db.add(ncr_item_2)
        db.flush()

        # Step 9 — Close NCR (D12 guard demonstration)
        # D12: Once status = CLOSED, no further items can be created or modified.
        #      The status guard fires in both create_item and update_item.
        #      ORDER: org check fires BEFORE status check (TN6 order).
        # In API usage: PATCH /non-conformance-reports/{id} {"status": "closed"}
        # Then: POST /non-conformance-reports/{id}/items → 400 (status guard fires)
        # We close the report here; the seed does not test the guard (tests do that).
        ncr_report.status = NCRStatus.CLOSED

        db.commit()

        # ── Print summary ──────────────────────────────────────────────────────

        print("Dev seed complete (Sprint 1 + 2 + 3 + 4).")
        print()
        print(f"  Organization : {org.name} ({org.code})")
        print(f"  org_id       : {org.id}")
        print()
        for u in USERS:
            user_obj = users[u["email"]]
            print(f"  User ({u['role_code']:10s}) : {u['email']}  /  {u['password']}")
            print(f"    user_id      : {user_obj.id}")
        print()
        n_foundation = sum(1 for p in PERMISSIONS if p["module_name"] == "foundation")
        n_commercial = sum(1 for p in PERMISSIONS if p["module_name"] == "commercial")
        n_production = sum(1 for p in PERMISSIONS if p["module_name"] == "production")
        n_quality    = sum(1 for p in PERMISSIONS if p["module_name"] == "quality")
        print(f"  Roles        : {', '.join(roles.keys())}")
        print(f"  Permissions  : {len(perms)}  ({n_foundation} foundation + {n_commercial} commercial + {n_production} production + {n_quality} quality)")
        print(f"  admin        : all {len(perms)} permissions")
        print(f"  super_admin  : all {len(perms)} permissions")
        print(f"  org_admin    : {len(ORG_ADMIN_PERMISSION_CODES)} foundation/read permissions")
        print(f"  commercial_manager : {len(COMMERCIAL_MANAGER_PERMISSION_CODES)} commercial permissions")
        print(f"  production_manager : {len(PRODUCTION_MANAGER_PERMISSION_CODES)} production permissions")
        print(f"  quality_manager    : {len(QUALITY_MANAGER_PERMISSION_CODES)} quality permissions")
        print(f"  production_supervisor : {len(PRODUCTION_SUPERVISOR_PERMISSION_CODES)} production floor permissions")
        print(f"  sales_rep    : {len(SALES_REP_PERMISSION_CODES)} sales permissions")
        print(f"  quality_inspector : {len(QUALITY_INSPECTOR_PERMISSION_CODES)} quality inspection permissions")
        print()
        print("  ── Commercial ──────────────────────────────────────────────────")
        print(f"  Customers    : {len(customers)}  ({', '.join(c['customer_code'] for c in CUSTOMERS)})")
        print(f"  Interactions : 1  (on CUST-001)")
        print(f"  Follow-ups   : 1  (on CUST-001, due in 4 days)")
        print(f"  Samples      : 1  (SAMP-001 on CUST-002, status=evaluated)")
        print(f"  Evaluations  : 1  (SAMP-001, result=accepted)")
        print(f"  Quotes       : 1  (Q-2026-001, status=issued, total=SAR {_total:,.2f})")
        print(f"  Orders       : 1  (ORD-2026-001, status=confirmed)")
        print()
        print("  ── Production ──────────────────────────────────────────────────")
        print(f"  Work Centers : 2  (WC-001 extrusion / WC-002 packing)")
        print(f"  Shifts       : 3  (SHIFT-MORN 07-15 / SHIFT-EVE 15-23 / SHIFT-NIGHT 23-07)")
        print(f"    ★ SHIFT-NIGHT crosses_midnight = True  (Sprint 3 edge case, D5)")
        print(f"  Prod Orders  : 2  (PO-001 in_progress urgent / PO-002 draft normal)")
        print(f"  Items        : 2  (on PO-001: line 1 wide roll / line 2 narrow roll)")
        print(f"  Shift Report : 1  (PO-001 morning shift, status=submitted)")
        print(f"  Prod Output  : 1  (PO-001 WC-001, 850 kg, status=recorded)")
        print(f"  Downtime     : 2")
        print(f"    DT-001: OPEN  — no end_time, status=open, duration_minutes=NULL  (D3/D4)")
        print(f"    DT-002: CLOSED — 45 min setup stop, status=closed, duration_minutes=45  (D3/D4)")
        print(f"  Waste        : 1  (PO-001 startup_loss 25 kg, no status field  D7)")
        print()
        print("  ── Quality & NCR ───────────────────────────────────────────────")
        print(f"  Quality Check  : 1  (QI-2026-0001, in_process_inspection, status=open, result=null  D1/D3)")
        print(f"    check_type   : in_process_inspection  (business type — NOT visual/dimension  D4)")
        print(f"    qty          : inspected=100, accepted=85, rejected=15  (85+15=100 ✓  D2)")
        print(f"  Quality Defect : 1  (category=thickness, severity=major, defect_count=15  D5/D6/D7)")
        print(f"    parent       : linked to QI-2026-0001  (quality_check_id required  D5)")
        print(f"  Rejection      : 1  (dimension_failure, disposition=rework  D8/D9)")
        print(f"    disposition_status : executed  (pending→executed transition demonstrated  D9)")
        print(f"    rejection_notes    : required non-empty text  (Quality PRD BR-02  D8)")
        print(f"  NCR Report     : 1  (NCR-2026-0001, status=closed  D10/D11)")
        print(f"    report_number: NCR-2026-0001  (auto-generated NCR-YYYY-NNNN  D11)")
        print(f"    source_type  : incoming_material  /  report_type: material_non_conformance")
        print(f"    lifecycle    : draft → open → under_review → closed  (D11/D12)")
        print(f"  NCR Items      : 2  (line_no 1 and 2 — auto-assigned  D13)")
        print(f"    item 1       : LLDPE Grade A, 500 kg, moisture deviation")
        print(f"    item 2       : LLDPE Grade B, 250 kg, color deviation")
        print(f"    ★ NCR closed — D12 guard active: no further items can be added")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
