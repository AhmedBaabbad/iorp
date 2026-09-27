"""Backfill scope=own for sales_rep's pre-existing customers/follow_ups/interactions:read grants.

_seed_roles() only INSERTs missing role-permission pairs; it never updates the
scope of a pair that already existed before ORG-RBAC-004 shipped. Organizations
provisioned before this feature therefore kept scope="organization" (the
migration's server_default) for sales_rep's read grants instead of the intended
"own". This is a one-time data backfill for exactly that gap -- it must not
touch any other role or any org where sales_rep already has the correct scope.
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2g2"
down_revision = "f6a1b2g1"
branch_labels = None
depends_on = None

_TARGET_CODES = (
    "commercial:customers:read",
    "commercial:follow_ups:read",
    "commercial:interactions:read",
)


def upgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE foundation_role_permissions rp
            SET scope = 'own'
            FROM foundation_roles r, foundation_permissions p
            WHERE rp.role_id = r.id
              AND rp.permission_id = p.id
              AND r.code = 'sales_rep'
              AND r.is_system = true
              AND p.code = ANY(:codes)
              AND rp.scope = 'organization'
            """
        ),
        {"codes": list(_TARGET_CODES)},
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE foundation_role_permissions rp
            SET scope = 'organization'
            FROM foundation_roles r, foundation_permissions p
            WHERE rp.role_id = r.id
              AND rp.permission_id = p.id
              AND r.code = 'sales_rep'
              AND r.is_system = true
              AND p.code = ANY(:codes)
              AND rp.scope = 'own'
            """
        ),
        {"codes": list(_TARGET_CODES)},
    )
