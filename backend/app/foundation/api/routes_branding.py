import base64
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Response
from sqlalchemy.orm import Session
from app.dependencies import get_db, require_permission
from app.core.storage import InvalidLogoError
from app.foundation.application.branding_service import BrandingService
from app.foundation.api.branding_schemas import BrandingUpdate

router = APIRouter(prefix='/organization/branding', tags=['organization-branding'])

@router.get('')
def get(current=Depends(require_permission('organization:branding:read')), db: Session = Depends(get_db)):
    return BrandingService(db).get_branding(current.tenant.organization_id)

@router.put('')
def update(data: BrandingUpdate, current=Depends(require_permission('organization:branding:update')), db: Session = Depends(get_db)):
    return BrandingService(db).update(current.tenant.organization_id, data, current.user.id)

@router.post('/logo')
async def upload(secondary: bool = False, file: UploadFile = File(...), current=Depends(require_permission('organization:branding:update')), db: Session = Depends(get_db)):
    try:
        return BrandingService(db).upload(current.tenant.organization_id, await file.read(2 * 1024 * 1024 + 1), current.user.id, secondary)
    except InvalidLogoError as exc:
        raise HTTPException(422, detail=str(exc)) from exc

@router.delete('/logo')
def remove(secondary: bool = False, current=Depends(require_permission('organization:branding:update')), db: Session = Depends(get_db)):
    return BrandingService(db).remove(current.tenant.organization_id, current.user.id, secondary)

@router.get('/logo')
def logo(secondary: bool = False, current=Depends(require_permission('organization:branding:read')), db: Session = Depends(get_db)):
    data = BrandingService(db).get_branding(current.tenant.organization_id)
    uri = data['secondary_logo_data_uri' if secondary else 'logo_data_uri']
    if not uri:
        raise HTTPException(404)
    header, encoded = uri.split(',', 1)
    return Response(base64.b64decode(encoded), media_type=header[5:].split(';')[0], headers={'Cache-Control': 'private, no-store'})
