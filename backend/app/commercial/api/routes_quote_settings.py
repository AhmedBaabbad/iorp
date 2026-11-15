from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.commercial.api.quote_settings_schemas import QuoteSettingsRead, QuoteSettingsUpdate
from app.commercial.application.quote_settings_service import QuoteSettingsService
from app.dependencies import get_db, require_permission, require_any_permission

router = APIRouter(prefix="/quote-settings", tags=["commercial-quote-settings"])


@router.get("/validity")
def quote_validity(current=Depends(require_any_permission(["commercial:quotes:create", "commercial:quotes:update", "commercial:quote_settings:read"])), db: Session = Depends(get_db)):
    """Validity and document language needed by editors; no private document administration settings."""
    service = QuoteSettingsService(db, current.tenant.organization_id)
    return {"quote_validity_days": service.validity_days(), "document_language": service.language()}


@router.get("", response_model=QuoteSettingsRead)
def read_quote_settings(current=Depends(require_permission("commercial:quote_settings:read")), db: Session = Depends(get_db)):
    """The signature and the terms and conditions printed on every quotation."""
    return QuoteSettingsService(db, current.tenant.organization_id).read()


@router.put("", response_model=QuoteSettingsRead)
def update_quote_settings(data: QuoteSettingsUpdate, current=Depends(require_permission("commercial:quote_settings:update")),
                          db: Session = Depends(get_db)):
    return QuoteSettingsService(db, current.tenant.organization_id).update(data, current.user.id)
