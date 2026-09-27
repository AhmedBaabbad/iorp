from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.storage import InvalidLogoError, LocalFileStorage
from app.dependencies import CurrentUserContext, get_db, require_permission
from app.foundation.api.schemas import OrganizationLogoResponse, OrganizationProfileResponse, OrganizationProfileUpdate
from app.foundation.application.organization_profile import InvalidTimezoneError, OrganizationProfileService

router = APIRouter(prefix="/organization", tags=["organization-profile"])


def _service(db: Session) -> OrganizationProfileService:
    return OrganizationProfileService(db)


@router.get("/profile", response_model=OrganizationProfileResponse)
def profile(current: CurrentUserContext = Depends(require_permission("foundation:organization:read")), db: Session = Depends(get_db)):
    service = _service(db)
    return service.response(service.get(current.tenant.organization_id))


@router.patch("/profile", response_model=OrganizationProfileResponse)
async def update_profile(request: Request, current: CurrentUserContext = Depends(require_permission("foundation:organization:update")), db: Session = Depends(get_db)):
    payload = await request.json()
    if "code" in payload:
        return JSONResponse(status_code=400, content={"code": "ORG_CODE_IMMUTABLE", "message": "Organization code cannot be changed"})
    payload.pop("status", None); payload.pop("organization_id", None)
    try:
        data = OrganizationProfileUpdate.model_validate(payload)
        service = _service(db)
        return service.response(service.update(current.tenant.organization_id, data, current.user))
    except InvalidTimezoneError as exc:
        return JSONResponse(status_code=400, content={"code": "INVALID_TIMEZONE", "message": str(exc)})
    except ValidationError as exc:
        return JSONResponse(status_code=400, content={"code": "INVALID_PROFILE", "message": str(exc.errors()[0]["msg"])})


@router.post("/logo", response_model=OrganizationLogoResponse)
async def upload_logo(file: UploadFile = File(...), current: CurrentUserContext = Depends(require_permission("foundation:organization:branding")), db: Session = Depends(get_db)):
    content = await file.read(2 * 1024 * 1024 + 1)
    try:
        _service(db).replace_logo(current.tenant.organization_id, content, current.user)
    except InvalidLogoError as exc:
        return JSONResponse(status_code=400, content={"code": "INVALID_LOGO", "message": str(exc)})
    return OrganizationLogoResponse(message="Logo uploaded successfully", logo_url="/api/v1/organization/logo", has_logo=True)


@router.delete("/logo", response_model=OrganizationLogoResponse)
def remove_logo(current: CurrentUserContext = Depends(require_permission("foundation:organization:branding")), db: Session = Depends(get_db)):
    removed = _service(db).remove_logo(current.tenant.organization_id, current.user)
    if not removed:
        raise HTTPException(status_code=404, detail="Logo not found.")
    return OrganizationLogoResponse(message="Logo removed successfully", has_logo=False)


@router.get("/logo")
def serve_logo(current: CurrentUserContext = Depends(require_permission("foundation:organization:read")), db: Session = Depends(get_db)):
    organization = _service(db).get(current.tenant.organization_id)
    if not organization.logo_path:
        raise HTTPException(status_code=404, detail="Logo not found.")
    storage = LocalFileStorage(); path = storage.resolve(organization.logo_path)
    if not path.is_file(): raise HTTPException(status_code=404, detail="Logo not found.")
    media = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}.get(path.suffix.lstrip("."))
    return FileResponse(path, media_type=media, headers={"Cache-Control": "public, max-age=3600"})
