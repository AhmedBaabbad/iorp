"""Seed one organization, two users, roles, permissions, customers, and sample
commercial data for local development.  Safe to run multiple times — skips if
the dev-org already exists.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.commercial.domain.enums import (
    CustomerStatus,
    FollowUpStatus,
    InteractionType,
    PriorityLevel,
    RelationshipStage,
)
from app.commercial.infrastructure.models import Customer, CustomerInteraction, FollowUp
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
]

ROLES = [
    dict(name="Admin",    code="admin",    description="Full access to all modules."),
    dict(name="Sales Rep", code="sales_rep", description="Commercial module access."),
]

USERS = [
    dict(full_name="Dev Admin",    email="admin@iorp-dev.com",  password="Admin1234!", role_code="admin"),
    dict(full_name="Sales Rep",    email="sales@iorp-dev.com",  password="Sales1234!", role_code="sales_rep"),
]

CUSTOMERS = [
    dict(customer_code="CUST-001", name="TechCorp Industries",    sector="Technology",  city="Dubai",    country="UAE",   relationship_stage=RelationshipStage.LEAD,     priority_level=PriorityLevel.HIGH,   notes="Warm lead from referral."),
    dict(customer_code="CUST-002", name="BuildCo Contracting",    sector="Construction", city="Abu Dhabi", country="UAE",  relationship_stage=RelationshipStage.PROSPECT, priority_level=PriorityLevel.MEDIUM, notes="Submitted a quote in May."),
    dict(customer_code="CUST-003", name="RetailPlus Distribution", sector="Retail",      city="Sharjah",  country="UAE",  relationship_stage=RelationshipStage.CUSTOMER, priority_level=PriorityLevel.LOW,    notes="Existing account, low activity."),
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

    finally:
        db.close()


if __name__ == "__main__":
    seed()
