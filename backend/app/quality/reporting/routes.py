"""Lookups for the quality report forms: inspections, orders and products, each needing the data's own read permission."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.reporting.registry import registry
from app.core.reporting.routes import can_for
from app.dependencies import get_current_user, get_db, permission_checked_in_handler
from app.quality.domain import permissions as Q
from app.quality.domain import report_permissions as R
from app.quality.infrastructure.models import QualityCheck
from app.quality.reporting.builders import shared

router = APIRouter(tags=['quality-reports'])
# Order numbers and products appear in every quality list, so reading any quality record is enough for them.
QUALITY_READS = (Q.CHECKS_READ, Q.REJECTIONS_READ, Q.DEFECTS_READ)
LOOKUP_PERMISSIONS = {'checks': (Q.CHECKS_READ,), 'orders': QUALITY_READS, 'products': QUALITY_READS}


@router.get('/reports/quality/lookups/{kind}', dependencies=[Depends(permission_checked_in_handler(*R.ALL, *QUALITY_READS))])
def lookups(kind: str, q: str = Query('', max_length=100), current=Depends(get_current_user), db: Session = Depends(get_db)):
    can = can_for(current)
    if not any(can(d.permission) for d in registry.definitions.values() if d.module == 'quality'):
        raise HTTPException(403)
    if kind not in LOOKUP_PERMISSIONS:
        raise HTTPException(404)
    if not any(can(p) for p in LOOKUP_PERMISSIONS[kind]):
        raise HTTPException(403, 'LOOKUP_FORBIDDEN')
    org = current.tenant.organization_id
    if kind == 'checks':
        rows = db.execute(select(QualityCheck.id, QualityCheck.inspection_code).where(
            QualityCheck.organization_id == org, QualityCheck.inspection_code.contains(q, autoescape=True))
            .order_by(QualityCheck.check_datetime.desc()).limit(100))
        return [dict(id=i, label=code) for i, code in rows]
    orders = shared('production_orders')
    if kind == 'products':
        values = db.scalars(select(orders.product_type).where(orders.organization_id == org, orders.product_type.contains(q, autoescape=True))
                            .distinct().order_by(orders.product_type).limit(100)).all()
        return [dict(id=v, label=v) for v in values]
    rows = db.execute(select(orders.id, orders.production_order_number, orders.product_type).where(
        orders.organization_id == org, orders.production_order_number.contains(q, autoescape=True))
        .order_by(orders.production_order_number.desc()).limit(100))
    return [dict(id=i, label=f'{number} — {product}') for i, number, product in rows]
