"""Seed one organization, two users, roles, permissions, customers, and Slice 2
commercial data (samples, evaluations, quotes, orders) for local development.
Skips if the dev-org already exists — drop and re-create the database to re-seed.
"""

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.db import SessionLocal
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

# ── Seed constants ────────────────────────────────────────────────────────────

ORG_CODE = "dev-org"

PERMISSIONS = [
    dict(code="commercial:customers:read",       name="Read Customers",       module_name="commercial", action_name="customers:read"),
    dict(code="commercial:customers:write",      name="Write Customers",      module_name="commercial", action_name="customers:write"),
    dict(code="commercial:interactions:read",    name="Read Interactions",    module_name="commercial", action_name="interactions:read"),
    dict(code="commercial:interactions:write",   name="Write Interactions",   module_name="commercial", action_name="interactions:write"),
    dict(code="commercial:follow_ups:read",      name="Read Follow-ups",      module_name="commercial", action_name="follow_ups:read"),
    dict(code="commercial:follow_ups:write",     name="Write Follow-ups",     module_name="commercial", action_name="follow_ups:write"),
    dict(code="commercial:samples:read",         name="Read Samples",         module_name="commercial", action_name="samples:read"),
    dict(code="commercial:samples:write",        name="Write Samples",        module_name="commercial", action_name="samples:write"),
    dict(code="commercial:quotes:read",          name="Read Quotes",          module_name="commercial", action_name="quotes:read"),
    dict(code="commercial:quotes:write",         name="Write Quotes",         module_name="commercial", action_name="quotes:write"),
    dict(code="commercial:orders:read",          name="Read Orders",          module_name="commercial", action_name="orders:read"),
    dict(code="commercial:orders:write",         name="Write Orders",         module_name="commercial", action_name="orders:write"),
]

ROLES = [
    dict(name="Admin",     code="admin",     description="Full access to all modules."),
    dict(name="Sales Rep", code="sales_rep", description="Commercial module access."),
]

USERS = [
    dict(full_name="Dev Admin", email="admin@iorp-dev.com", password="Admin1234!", role_code="admin"),
    dict(full_name="Sales Rep", email="sales@iorp-dev.com", password="Sales1234!", role_code="sales_rep"),
]

CUSTOMERS = [
    dict(customer_code="CUST-001", name="TechCorp Industries",     sector="Technology",   city="Dubai",     country="UAE", relationship_stage=RelationshipStage.LEAD,     priority_level=PriorityLevel.HIGH,   notes="Warm lead from referral."),
    dict(customer_code="CUST-002", name="BuildCo Contracting",     sector="Construction", city="Abu Dhabi", country="UAE", relationship_stage=RelationshipStage.CUSTOMER, priority_level=PriorityLevel.MEDIUM, notes="Submitted a quote in May."),
    dict(customer_code="CUST-003", name="RetailPlus Distribution", sector="Retail",       city="Sharjah",   country="UAE", relationship_stage=RelationshipStage.CUSTOMER, priority_level=PriorityLevel.LOW,    notes="Existing account, low activity."),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Main seed ─────────────────────────────────────────────────────────────────

def seed() -> None:
    db = SessionLocal()
    try:
        existing_org = db.query(Organization).filter_by(code=ORG_CODE).first()
        if existing_org:
            print("Seed data already exists — skipping.")
            print(f"  org_id  : {existing_org.id}")
            return

        # Organization
        org = Organization(
            name="Dev Organization",
            code=ORG_CODE,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
        )
        db.add(org)
        db.flush()

        # Permissions (global — not org-scoped)
        perms = {p["code"]: _get_or_create_permission(db, p) for p in PERMISSIONS}

        # Roles
        roles = {r["code"]: _get_or_create_role(db, org.id, r) for r in ROLES}

        # Assign all permissions to both roles (MVP: same access)
        for role in roles.values():
            for perm in perms.values():
                _assign_permission(db, role.id, perm.id)

        # Users
        users = {}
        for u in USERS:
            role = roles[u["role_code"]]
            users[u["email"]] = _get_or_create_user(db, org.id, u, role.id)

        admin_user = users["admin@iorp-dev.com"]

        # Customers
        customers = []
        for c in CUSTOMERS:
            obj = Customer(
                organization_id=org.id,
                status=CustomerStatus.ACTIVE,
                **c,
            )
            db.add(obj)
            customers.append(obj)
        db.flush()

        # Sample interaction on CUST-001
        interaction = CustomerInteraction(
            customer_id=customers[0].id,
            interaction_type=InteractionType.CALL,
            interaction_date=datetime.now(timezone.utc) - timedelta(days=3),
            subject="Initial discovery call",
            summary="Discussed current infrastructure needs and timeline. They are evaluating 3 vendors.",
            outcome="Positive — requested a formal proposal.",
            next_step_hint="Send proposal by end of week.",
            created_by_user_id=admin_user.id,
        )
        db.add(interaction)
        db.flush()

        # Sample follow-up on CUST-001
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

        # ── Slice 2 seed data ─────────────────────────────────────────────────

        # Sample SAMP-001 on CUST-002 (BuildCo Contracting)
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

        # Sample evaluation on SAMP-001
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

        # Quote Q-2026-001 on CUST-002, linked to SAMP-001
        _subtotal = Decimal("3010.00")
        _discount = Decimal("60.00")
        _tax = Decimal("0.00")
        _total = _subtotal - _discount + _tax
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
                QuoteItem(
                    line_no=1,
                    product_type="Steel Rod",
                    quantity=Decimal("500.00"),
                    unit="kg",
                    unit_price=Decimal("4.50"),
                    line_total=Decimal("2250.00"),
                ),
                QuoteItem(
                    line_no=2,
                    product_type="Rebar",
                    quantity=Decimal("200.00"),
                    unit="kg",
                    unit_price=Decimal("3.80"),
                    line_total=Decimal("760.00"),
                ),
            ],
        )
        db.add(quote)
        db.flush()

        # Commercial order ORD-2026-001 on CUST-002, linked to Q-2026-001
        order = CommercialOrder(
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
                CommercialOrderItem(
                    line_no=1,
                    product_type="Steel Rod",
                    quantity=Decimal("500.00"),
                    unit="kg",
                    agreed_unit_price=Decimal("4.50"),
                    line_total=Decimal("2250.00"),
                ),
                CommercialOrderItem(
                    line_no=2,
                    product_type="Rebar",
                    quantity=Decimal("200.00"),
                    unit="kg",
                    agreed_unit_price=Decimal("3.80"),
                    line_total=Decimal("760.00"),
                ),
            ],
        )
        db.add(order)

        db.commit()

        # Print summary
        print("Dev seed complete.")
        print()
        print(f"  Organization : {org.name} ({org.code})")
        print(f"  org_id       : {org.id}")
        print()
        for u in USERS:
            user_obj = users[u["email"]]
            print(f"  User ({u['role_code']:10s}) : {u['email']}  /  {u['password']}")
            print(f"    user_id      : {user_obj.id}")
        print()
        print(f"  Roles        : {', '.join(roles.keys())}")
        print(f"  Permissions  : {len(perms)}")
        print(f"  Customers    : {len(customers)}  ({', '.join(c['customer_code'] for c in CUSTOMERS)})")
        print(f"  Interactions : 1  (on {customers[0].customer_code})")
        print(f"  Follow-ups   : 1  (on {customers[0].customer_code}, due in 4 days)")
        print()
        print(f"  Samples      : 1  (SAMP-001 on CUST-002, status=evaluated)")
        print(f"  Evaluations  : 1  (on SAMP-001, result=accepted, next=proceed_to_quote)")
        print(f"  Quotes       : 1  (Q-2026-001 on CUST-002, status=issued, total=SAR {_total:,.2f})")
        print(f"  Orders       : 1  (ORD-2026-001 on CUST-002, status=confirmed)")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
