"""The organization's audit trail (ORG-AUDIT-002): read only — no endpoint creates, changes or deletes an entry."""
from datetime import datetime, timezone
import csv
from io import StringIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, page_of, page_params, paginate
from app.dependencies import CurrentUserContext, get_db, require_permission
from app.foundation.domain.audit_labels import ENTITIES, action_label, entity_label
from app.foundation.domain.permission_catalog import PERMISSION_BY_CODE
from app.foundation.infrastructure.models import TenantAuditEntry as A

router = APIRouter(prefix="/audit-log", tags=["Tenant Audit"])
READ = require_permission("foundation:audit:read")
ENTITY_PATTERN = "^(" + "|".join(ENTITIES) + ")$"


def _filtered(organization_id, *, entity_type=None, action=None, actor_id=None, date_from=None, date_to=None, search=None):
    query = select(A).where(A.organization_id == organization_id)
    if entity_type:
        query = query.where(A.entity_type == entity_type)
    if action:
        query = query.where(A.action == action)
    if actor_id:
        query = query.where(A.actor_id == actor_id)
    if date_from:
        query = query.where(A.created_at >= date_from)
    if date_to:
        query = query.where(A.created_at <= date_to)
    if search and search.strip():
        like = f"%{search.strip()}%"
        query = query.where(or_(A.entity_name.ilike(like), A.actor_name.ilike(like)))
    return query


def _permission_names(details) -> dict:
    """The permission codes an entry mentions, with their names in both languages (the screens show names, not codes)."""
    codes = set()
    if isinstance(details, dict):
        for key in ("permission", "permission_code"):
            if isinstance(details.get(key), str):
                codes.add(details[key])
    return {c: dict(ar=PERMISSION_BY_CODE[c].name_ar, en=PERMISSION_BY_CODE[c].name_en) for c in codes if c in PERMISSION_BY_CODE}


def _view(entry: A) -> dict:
    return dict(id=entry.id, created_at=entry.created_at, action=entry.action, entity_type=entry.entity_type, entity_id=entry.entity_id,
                entity_name=entry.entity_name, actor_id=entry.actor_id, actor_name=entry.actor_name, details=entry.details,
                permission_names=_permission_names(entry.details))


@router.get("")
def list_tenant_audit(entity_type: str | None = Query(None, pattern=ENTITY_PATTERN), action: str | None = Query(None, max_length=80),
                      actor_id: UUID | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
                      search: str | None = Query(None, max_length=120), params: PageParams = Depends(page_params),
                      current: CurrentUserContext = Depends(READ), db: Session = Depends(get_db)):
    """One page of the trail, newest first (ARCH-PAGE-001)."""
    query = _filtered(current.tenant.organization_id, entity_type=entity_type, action=action, actor_id=actor_id,
                      date_from=date_from, date_to=date_to, search=search)
    rows, total = paginate(db, query.order_by(A.created_at.desc(), A.id.desc()), params)
    return page_of([_view(r) for r in rows], total, params)


@router.get("/export")
def export_tenant_audit(locale: str = Query("ar", pattern="^(ar|en)$"), entity_type: str | None = Query(None, pattern=ENTITY_PATTERN),
                        action: str | None = Query(None, max_length=80), actor_id: UUID | None = None, date_from: datetime | None = None,
                        date_to: datetime | None = None, search: str | None = Query(None, max_length=120),
                        current: CurrentUserContext = Depends(READ), db: Session = Depends(get_db)):
    rows = db.scalars(_filtered(current.tenant.organization_id, entity_type=entity_type, action=action, actor_id=actor_id,
                                date_from=date_from, date_to=date_to, search=search).order_by(A.created_at.desc()).limit(10_000))
    ar = locale == "ar"
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["الوقت", "العملية", "نوع السجل", "على", "بواسطة"] if ar else ["Time", "Action", "Record", "On", "By"])
    for entry in rows:
        values = [entry.created_at.isoformat(), action_label(entry.action, locale), entity_label(entry.entity_type, locale), entry.entity_name,
                  entry.actor_name or ("النظام" if ar else "The system")]
        writer.writerow([("'" + str(v)) if v is not None and str(v).startswith(("=", "+", "-", "@")) else v for v in values])
    filename = f"organization-audit-{datetime.now(timezone.utc).date().isoformat()}.csv"
    return Response(content=("﻿" + stream.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{entry_id}")
def get_tenant_audit(entry_id: UUID, current: CurrentUserContext = Depends(READ), db: Session = Depends(get_db)):
    entry = db.scalar(select(A).where(A.id == entry_id, A.organization_id == current.tenant.organization_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="Audit entry not found.")
    return _view(entry)
