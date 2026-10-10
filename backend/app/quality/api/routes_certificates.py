"""Certificates of Analysis (QUAL-COA-001). One permission per action; errors answer {"code": ...}."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.reporting.routes import generate_response
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_current_user, get_db, permission_check, permission_checked_in_handler, require_permission
from app.quality.api.certificate_schemas import (
    CertificateCreate, CertificateListItem, CertificateRead, CertificateSources, CertificateUpdate, RevokeInput, SettingsRead, SettingsUpdate,
)
from app.quality.application.certificate_service import CertificateService
from app.quality.domain import permissions as Q
from app.quality.domain.rules import QualityError

router = APIRouter(tags=["quality-certificates"])
PATH = "/quality-certificates"


def _error(exc: QualityError):
    return HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail})


def _can(can):
    return lambda action: can(f"quality:certificates:{action}")


def _read(service, certificate, can, detail=True):
    model = CertificateRead if detail else CertificateListItem
    return model.model_validate({**model.model_validate(certificate).model_dump(), **service.views([certificate], _can(can), detail)[0]})


@router.get("/quality-settings", response_model=SettingsRead, dependencies=[Depends(require_permission(Q.COA_READ))])
def read_settings(tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    settings = CertificateService(db, tenant).settings()
    db.commit()
    return settings


@router.patch("/quality-settings", response_model=SettingsRead, dependencies=[Depends(require_permission(Q.SETTINGS_UPDATE))])
def update_settings(payload: SettingsUpdate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Certificate numbering: prefix and the last number used (to continue from paper; never backwards)."""
    try:
        return CertificateService(db, tenant).update_settings(payload)
    except QualityError as exc:
        raise _error(exc) from exc


@router.get(f"{PATH}/sources", response_model=CertificateSources, dependencies=[Depends(require_permission(Q.COA_CREATE))])
def certificate_sources(check_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Whether this inspection can be certified, and the customers its lot was made for."""
    try:
        return CertificateService(db, tenant).sources(check_id)
    except QualityError as exc:
        raise _error(exc) from exc


@router.get(PATH, response_model=list[CertificateListItem], dependencies=[Depends(require_permission(Q.COA_READ))])
def list_certificates(status_filter: str | None = Query(default=None, alias="status", pattern="^(draft|issued|revoked)$"),
                      quality_check_id: UUID | None = None, production_order_id: UUID | None = None,
                      search: str | None = Query(default=None, max_length=60),
                      tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    service = CertificateService(db, tenant)
    rows = service.list(status_filter, quality_check_id, production_order_id, search)
    return [CertificateListItem.model_validate({**CertificateListItem.model_validate(c).model_dump(), **v})
            for c, v in zip(rows, service.views(rows, _can(can)))]


@router.post(PATH, response_model=CertificateRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Q.COA_CREATE))])
def create_certificate(payload: CertificateCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                       can=Depends(permission_check)):
    """A draft from a closed, conforming inspection; its results are copied and frozen."""
    service = CertificateService(db, tenant)
    try:
        return _read(service, service.create(payload), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.get(f"{PATH}/{{certificate_id}}", response_model=CertificateRead, dependencies=[Depends(require_permission(Q.COA_READ))])
def get_certificate(certificate_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    service = CertificateService(db, tenant)
    try:
        return _read(service, service.get(certificate_id), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.patch(f"{PATH}/{{certificate_id}}", response_model=CertificateRead, dependencies=[Depends(require_permission(Q.COA_UPDATE))])
def update_certificate(certificate_id: UUID, payload: CertificateUpdate, tenant: TenantContext = Depends(get_current_tenant),
                       db: Session = Depends(get_db), can=Depends(permission_check)):
    service = CertificateService(db, tenant)
    try:
        return _read(service, service.update(certificate_id, payload), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.post(f"{PATH}/{{certificate_id}}/issue", response_model=CertificateRead,
             dependencies=[Depends(require_permission(Q.COA_ISSUE)), Depends(permission_checked_in_handler(Q.COA_REVOKE))])
def issue_certificate(certificate_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """Approves and numbers the certificate; it becomes final. A replacement also revokes the certificate it replaces, so
    issuing one needs the permission to revoke as well (RBAC-002)."""
    service = CertificateService(db, tenant)
    try:
        if service.get(certificate_id).supersedes_id is not None and not can(Q.COA_REVOKE):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Issuing a replacement revokes the original: it needs the revoke permission too.")
        return _read(service, service.issue(certificate_id), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.post(f"{PATH}/{{certificate_id}}/revoke", response_model=CertificateRead, dependencies=[Depends(require_permission(Q.COA_REVOKE))])
def revoke_certificate(certificate_id: UUID, payload: RevokeInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                       can=Depends(permission_check)):
    service = CertificateService(db, tenant)
    try:
        return _read(service, service.revoke(certificate_id, payload.reason), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.post(f"{PATH}/{{certificate_id}}/replace", response_model=CertificateRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(Q.COA_CREATE))])
def replace_certificate(certificate_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """A corrected draft; issuing it revokes the certificate it supersedes."""
    service = CertificateService(db, tenant)
    try:
        return _read(service, service.replace(certificate_id), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.get(f"{PATH}/{{certificate_id}}/document.pdf", dependencies=[Depends(require_permission(Q.COA_READ))])
def certificate_document(certificate_id: UUID, lang: str = Query("en", pattern="^(ar|en)$"), current=Depends(get_current_user), db: Session = Depends(get_db)):
    """The certificate as a PDF with the company's external identity; a draft carries a "not valid" mark."""
    return generate_response("quality.certificate", dict(certificate_id=str(certificate_id), lang=lang), "pdf", current, db)
