"""The single writer of the organization's quotation settings (signature and terms)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commercial.api.quote_settings_schemas import QuoteSettingsUpdate
from app.commercial.infrastructure.models import QuoteSettings, QuoteTerm

# Printed under "With best regards" until the organization sets its own title.
DEFAULT_SIGNATURE = ("مدير المبيعات", "Sales Manager")


class QuoteSettingsService:
    def __init__(self, db: Session, organization_id):
        self.db, self.org_id = db, organization_id

    def language(self) -> str:
        """The language quotations are printed in (Arabic until the organization chooses)."""
        row = self.db.get(QuoteSettings, self.org_id)
        return row.document_language if row and row.document_language in ('ar', 'en') else 'ar'

    def terms(self, active_only=False) -> list[QuoteTerm]:
        query = select(QuoteTerm).where(QuoteTerm.organization_id == self.org_id)
        if active_only:
            query = query.where(QuoteTerm.is_active.is_(True))
        return list(self.db.scalars(query.order_by(QuoteTerm.sort_order, QuoteTerm.id)))

    def validity_days(self) -> int:
        row = self.db.get(QuoteSettings, self.org_id)
        return row.quote_validity_days if row else 10

    def read(self) -> dict:
        row = self.db.get(QuoteSettings, self.org_id)
        return dict(
            quote_validity_days=self.validity_days(),
            document_language=row.document_language if row and row.document_language in ('ar', 'en') else 'ar',
            signature_title_ar=row.signature_title_ar if row and row.signature_title_ar else DEFAULT_SIGNATURE[0],
            signature_title_en=row.signature_title_en if row and row.signature_title_en else DEFAULT_SIGNATURE[1],
            show_preparer_name=bool(row and row.show_preparer_name),
            terms=[dict(title_ar=t.title_ar, title_en=t.title_en, body_ar=t.body_ar, body_en=t.body_en, is_active=t.is_active)
                   for t in self.terms()],
        )

    def update(self, data: QuoteSettingsUpdate, actor_id) -> dict:
        row = self.db.get(QuoteSettings, self.org_id, with_for_update=True)
        if row is None:
            row = QuoteSettings(organization_id=self.org_id)
            self.db.add(row)
        row.document_language = data.document_language
        row.quote_validity_days = data.quote_validity_days
        row.signature_title_ar, row.signature_title_en = data.signature_title_ar, data.signature_title_en
        row.show_preparer_name, row.updated_by_user_id = data.show_preparer_name, actor_id
        for old in self.terms():
            self.db.delete(old)
        self.db.flush()
        self.db.add_all(QuoteTerm(organization_id=self.org_id, sort_order=index, **term.model_dump())
                        for index, term in enumerate(data.terms))
        self.db.commit()
        return self.read()
