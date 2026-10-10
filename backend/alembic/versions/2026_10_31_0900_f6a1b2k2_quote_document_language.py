"""Quotation document language (QUOTE-DOC-002).

- commercial_quote_settings.document_language (ar | en, Arabic by default): every quotation is printed in it, with the
  settings written in that language only.
- commercial_quote_terms: the Arabic title and text become optional, so terms may be written in English only.
No existing data changes.
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a1b2k2"
down_revision = "f6a1b2k1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("commercial_quote_settings", sa.Column("document_language", sa.String(2), nullable=False, server_default="ar"))
    op.create_check_constraint("ck_commercial_quote_settings_document_language", "commercial_quote_settings", "document_language IN ('ar', 'en')")
    op.alter_column("commercial_quote_terms", "title_ar", existing_type=sa.String(120), nullable=True)
    op.alter_column("commercial_quote_terms", "body_ar", existing_type=sa.Text(), nullable=True)


def downgrade():
    # Terms written in English only keep their English text in the Arabic columns, which are required again.
    op.execute("UPDATE commercial_quote_terms SET title_ar = COALESCE(title_ar, title_en, ''), body_ar = COALESCE(body_ar, body_en, '')")
    op.alter_column("commercial_quote_terms", "body_ar", existing_type=sa.Text(), nullable=False)
    op.alter_column("commercial_quote_terms", "title_ar", existing_type=sa.String(120), nullable=False)
    op.drop_constraint("ck_commercial_quote_settings_document_language", "commercial_quote_settings", type_="check")
    op.drop_column("commercial_quote_settings", "document_language")
