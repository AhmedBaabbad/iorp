from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core import files
from app.core.storage import InvalidLogoError, LocalFileStorage
from app.dependencies import CurrentUserContext, get_current_user, get_db, require_permission, require_any_permission
from app.foundation.api.schemas import OrganizationLogoResponse, OrganizationProfileResponse, OrganizationProfileUpdate
from app.foundation.application.organization_profile import InvalidTimezoneError, OrganizationProfileService

router = APIRouter(prefix="/organization", tags=["organization-profile"])


def _service(db: Session) -> OrganizationProfileService:
    return OrganizationProfileService(db)


@router.get("/profile", response_model=OrganizationProfileResponse)
def profile(current: CurrentUserContext = Depends(require_any_permission(["foundation:organization:read", "organization:branding:read"])), db: Session = Depends(get_db)):
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
async def upload_logo(file: UploadFile = File(...), current: CurrentUserContext = Depends(require_any_permission(["foundation:organization:branding", "organization:branding:update"])), db: Session = Depends(get_db)):
    content = await file.read(files.read_limit('logo'))
    try:
        _service(db).replace_logo(current.tenant.organization_id, content, current.user)
    except InvalidLogoError as exc:
        return JSONResponse(status_code=400, content={"code": "INVALID_LOGO", "message": str(exc)})
    return OrganizationLogoResponse(message="Logo uploaded successfully", logo_url="/api/v1/organization/logo", has_logo=True)


@router.delete("/logo", response_model=OrganizationLogoResponse)
def remove_logo(current: CurrentUserContext = Depends(require_any_permission(["foundation:organization:branding", "organization:branding:update"])), db: Session = Depends(get_db)):
    removed = _service(db).remove_logo(current.tenant.organization_id, current.user)
    if not removed:
        raise HTTPException(status_code=404, detail="Logo not found.")
    return OrganizationLogoResponse(message="Logo removed successfully", has_logo=False)


@router.get("/storage")
def storage(current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    """What each kind of upload accepts (the one policy, core/files.py) and what the organization's files occupy against
    its quota. Any user of the organization reads it (the upload screens show the limits); only its own organization."""
    organization_id = current.tenant.organization_id
    used, quota = files.usage(db, organization_id), files.quota(db, organization_id)
    return dict(policy=files.policy(), used_bytes=used, quota_bytes=quota, percent=round(used * 100 / quota, 1) if quota else 0.0)


@router.get("/logo")
def serve_logo(current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    """The organization's logo for every one of its users (the sidebar shows it): reading it needs no permission, only a
    session of this organization, and the organization is the session's own, so no other organization's logo is reachable.
    Changing it stays with foundation:organization:branding / organization:branding:update."""
    organization = _service(db).get(current.tenant.organization_id)
    if not organization.logo_path:
        raise HTTPException(status_code=404, detail="Logo not found.")
    storage = LocalFileStorage(); path = storage.resolve(organization.logo_path)
    if not path.is_file(): raise HTTPException(status_code=404, detail="Logo not found.")
    media = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}.get(path.suffix.lstrip("."))
    return FileResponse(path, media_type=media, headers={"Cache-Control": "private, no-store"})
