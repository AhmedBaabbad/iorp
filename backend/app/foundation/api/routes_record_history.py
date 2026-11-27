from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.core.interfaces.record_history import can_read
from app.core.pagination import page_params, page_of, paginate, PageParams
from app.dependencies import get_db, get_current_tenant, permission_check, permission_checked_in_handler
from app.foundation.infrastructure.models import TenantActivityLog

router = APIRouter(tags=['record-history'])


@router.get('/record-history/{entity_type}/{entity_id}', dependencies=[Depends(permission_checked_in_handler('record_history:<entity.read>'))])
def history(entity_type: str, entity_id: UUID, params: PageParams = Depends(page_params),
            db=Depends(get_db), tenant=Depends(get_current_tenant), can=Depends(permission_check)):
    if not can_read(db, tenant, entity_type, entity_id, can):
        # Same response for absent/foreign/unauthorized entities; no existence leak.
        raise HTTPException(404, detail={'code': 'RECORD_HISTORY_UNAVAILABLE'})
    query = select(TenantActivityLog).where(TenantActivityLog.organization_id == tenant.organization_id,
        TenantActivityLog.entity_type == entity_type, TenantActivityLog.entity_id == entity_id
    ).order_by(TenantActivityLog.created_at.desc(), TenantActivityLog.id.desc())
    rows, total = paginate(db, query, params)
    return page_of([dict(id=r.id, action=r.action, actor_name=r.actor_name, actor_id=r.actor_id,
                        created_at=r.created_at, details=r.details) for r in rows], total, params)
