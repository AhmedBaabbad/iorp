"""Signatures of a document (PROJECT-GOV-004): who signed each approval step and on whose behalf.

Readable only by who may read the document itself: the module that owns it says so (core/interfaces/approvals.py).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.interfaces import approvals
from app.dependencies import CurrentUserContext, get_current_user, get_db

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/{resource_type}/{resource_id}")
def signatures(resource_type: str, resource_id: UUID, current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    if not approvals.visible(db, current.tenant, resource_type, resource_id):
        raise HTTPException(404, detail="NOT_FOUND")
    return approvals.signatures(db, current.tenant.organization_id, resource_type, [resource_id])[resource_id]
