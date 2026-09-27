"""audit, normalize and safely disambiguate login emails

Revision ID: f6a1b2e6
Revises: f6a1b2e5
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "f6a1b2e6"
down_revision: str | None = "f6a1b2e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    op.execute("UPDATE foundation_users SET email = LOWER(TRIM(email)) WHERE email <> LOWER(TRIM(email))")
    op.execute("UPDATE system_platform_accounts SET email = LOWER(TRIM(email)) WHERE email <> LOWER(TRIM(email))")

    duplicates = connection.execute(text("""
        SELECT lower(trim(email)) AS normalized_email, count(*) AS count
        FROM foundation_users GROUP BY lower(trim(email)) HAVING count(*) > 1
    """)).fetchall()
    for duplicate in duplicates:
        print(f"WARNING: duplicate tenant email detected: {duplicate.normalized_email} ({duplicate.count})")

    connection.execute(text("""
        WITH ranked AS (
          SELECT id, organization_id, email,
                 row_number() OVER (PARTITION BY lower(trim(email)) ORDER BY created_at, id) AS position
          FROM foundation_users
        )
        UPDATE foundation_users AS users
        SET email = left(split_part(users.email, '@', 1), 120)
                    || '+duplicate-' || replace(users.organization_id::text, '-', '')
                    || '@' || split_part(users.email, '@', 2)
        FROM ranked
        WHERE users.id = ranked.id AND ranked.position > 1
    """))

    overlaps = connection.execute(text("""
        SELECT fu.id, fu.organization_id, fu.email
        FROM foundation_users fu
        JOIN system_platform_accounts spa ON lower(trim(fu.email)) = lower(trim(spa.email))
    """)).fetchall()
    for overlap in overlaps:
        print(f"WARNING: tenant/platform email overlap resolved for tenant user {overlap.id}: {overlap.email}")
    connection.execute(text("""
        UPDATE foundation_users AS users
        SET email = left(split_part(users.email, '@', 1), 120)
                    || '+duplicate-' || replace(users.organization_id::text, '-', '')
                    || '@' || split_part(users.email, '@', 2)
        FROM system_platform_accounts AS accounts
        WHERE lower(trim(users.email)) = lower(trim(accounts.email))
    """))


def downgrade() -> None:
    # Normalization and safe disambiguation cannot be reversed reliably.
    pass
