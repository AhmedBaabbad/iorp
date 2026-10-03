from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.commercial.api.quote_settings_schemas import QuoteSettingsRead, QuoteSettingsUpdate
from app.commercial.application.quote_settings_service import QuoteSettingsService
from app.dependencies import get_db, require_permission

router = APIRouter(prefix="/quote-settings", tags=["commercial-quote-settings"])


@router.get("", response_model=QuoteSettingsRead)
def read_quote_settings(current=Depends(require_permission("commercial:quote_settings:read")), db: Session = Depends(get_db)):
    """The signature and the terms and conditions printed on every quotation."""
    return QuoteSettingsService(db, current.tenant.organization_id).read()


@router.put("", response_model=QuoteSettingsRead)
def update_quote_settings(data: QuoteSettingsUpdate, current=Depends(require_permission("commercial:quote_settings:update")),
                          db: Session = Depends(get_db)):
    return QuoteSettingsService(db, current.tenant.organization_id).update(data, current.user.id)
