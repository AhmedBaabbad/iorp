from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.dependencies import get_current_user, get_db, permission_checked_in_handler
from app.production.domain import permissions as P
from app.core.reporting.routes import generate_response, can_for
from app.production.reporting.builders import ProductionOrder, WorkCenter, shared
from app.core.reporting.registry import registry
from fastapi import HTTPException

router=APIRouter(tags=['production-reports'])
# A lookup lists one entity, so it needs that entity's read permission (and some production report).
LOOKUP_PERMISSION={'orders':P.ORDERS_READ,'products':P.ORDERS_READ,'centers':P.WORK_CENTERS_READ,'customers':'commercial:customers:read'}

@router.get('/production/production-orders/{order_id}/report.pdf',dependencies=[Depends(permission_checked_in_handler(P.REPORT_ORDER_FULL))])
def shortcut(order_id:UUID,lang:str='ar',orientation:str='portrait',sections:list[str]|None=Query(None),current=Depends(get_current_user),db:Session=Depends(get_db)):
    return generate_response('production.order_full',dict(order_id=str(order_id),lang=lang,orientation=orientation,sections=sections),'pdf',current,db)

@router.get('/reports/production/lookups/{kind}',dependencies=[Depends(permission_checked_in_handler(*P.REPORTS,*dict.fromkeys(LOOKUP_PERMISSION.values())))])
def lookups(kind:str,q:str=Query('',max_length=100),current=Depends(get_current_user),db:Session=Depends(get_db)):
    can=can_for(current)
    if not any(can(d.permission) for d in registry.definitions.values() if d.module=='production'):
        raise HTTPException(403)
    if kind not in LOOKUP_PERMISSION: raise HTTPException(404)
    if not can(LOOKUP_PERMISSION[kind]):
        raise HTTPException(403,'CUSTOMER_LOOKUP_FORBIDDEN' if kind=='customers' else 'LOOKUP_FORBIDDEN')
    org=current.tenant.organization_id
    if kind=='products':
        values=db.scalars(select(ProductionOrder.product_type).where(ProductionOrder.organization_id==org,ProductionOrder.product_type.contains(q,autoescape=True)).distinct().limit(100)).all()
        return [dict(id=v,label=v) for v in values]
    if kind=='customers':
        # Customer names belong to commercial: offered only to users who may read customers (checked above).
        customers=shared('commercial_customers')
        return [dict(id=i,label=name) for i,name in db.execute(select(customers.id,customers.name).where(
            customers.organization_id==org,customers.name.contains(q,autoescape=True)).order_by(customers.name).limit(100))]
    model,field={'orders':(ProductionOrder,ProductionOrder.production_order_number),'centers':(WorkCenter,WorkCenter.name)}.get(kind,(None,None))
    if model is None: raise HTTPException(404)
    return [dict(id=r.id,label=name) for r,name in db.execute(select(model,field).where(model.organization_id==org,field.contains(q,autoescape=True)).order_by(field).limit(100))]
