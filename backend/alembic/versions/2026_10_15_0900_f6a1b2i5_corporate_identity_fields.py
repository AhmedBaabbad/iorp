"""Corporate document identity (DOC-IDENTITY-001): Unified No. and the external-document tagline.

Adds foundation_organization_branding.unified_number, descriptor_ar and descriptor_en. These are company
identity, kept in the single identity source like the CR and VAT numbers. Existing values are not changed.
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a1b2i5"
down_revision = "f6a1b2i4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("foundation_organization_branding", sa.Column("unified_number", sa.String(10)))
    op.add_column("foundation_organization_branding", sa.Column("descriptor_ar", sa.String(255)))
    op.add_column("foundation_organization_branding", sa.Column("descriptor_en", sa.String(255)))


def downgrade():
    op.drop_column("foundation_organization_branding", "descriptor_en")
    op.drop_column("foundation_organization_branding", "descriptor_ar")
    op.drop_column("foundation_organization_branding", "unified_number")
