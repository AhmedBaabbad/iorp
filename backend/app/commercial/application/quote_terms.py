from sqlalchemy import select
from app.commercial.application.quote_settings_service import QuoteSettingsService
from app.commercial.infrastructure.quote_terms_models import QuoteTermsSnapshot


def current_terms(db, org):
    return [{key:getattr(term,key) for key in ('title_ar','title_en','body_ar','body_en')}
            for term in QuoteSettingsService(db,org).terms(active_only=True)]


def freeze(db, quote, actor):
    existing = db.scalar(select(QuoteTermsSnapshot).where(QuoteTermsSnapshot.organization_id==quote.organization_id,
        QuoteTermsSnapshot.quote_id==quote.id, QuoteTermsSnapshot.revision==quote.revision))
    if existing:
        raise ValueError('QUOTE_TERMS_ALREADY_FROZEN')
    db.add(QuoteTermsSnapshot(organization_id=quote.organization_id,quote_id=quote.id,revision=quote.revision,
        terms=current_terms(db,quote.organization_id),captured_by=actor,source='issued'))


def document_terms(db, quote):
    if quote.status == 'draft':
        return current_terms(db,quote.organization_id)
    snapshot = db.scalar(select(QuoteTermsSnapshot).where(QuoteTermsSnapshot.organization_id==quote.organization_id,
        QuoteTermsSnapshot.quote_id==quote.id, QuoteTermsSnapshot.revision==quote.revision))
    # No guessing old contractual text from today's settings if a legacy snapshot is missing.
    return snapshot.terms if snapshot else []


def terms_source(db, quote):
    if quote.status=='draft':return 'draft'
    return db.scalar(select(QuoteTermsSnapshot.source).where(QuoteTermsSnapshot.organization_id==quote.organization_id,
        QuoteTermsSnapshot.quote_id==quote.id,QuoteTermsSnapshot.revision==quote.revision)) or 'missing'
