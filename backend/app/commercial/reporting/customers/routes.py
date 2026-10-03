from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from app.core.reporting.routes import generate_response, can_for, REPORT_PERMISSION
from app.dependencies import get_current_user, get_db
from .queries import scoped
from .definitions import PERMISSIONS, READ, DEMAND
from . import providers
from app.commercial.infrastructure.models import Customer

router=APIRouter(tags=['customer reports'],dependencies=[REPORT_PERMISSION])


@router.get('/customers/{customer_id}/report.pdf')
def customer_pdf(customer_id:UUID, lang:str='ar', audience:str='customer', sections:str|None=None,
                 current=Depends(get_current_user),db=Depends(get_db)):
    params=dict(customer_id=str(customer_id),lang=lang,audience=audience)
    if sections is not None:params['sections']=sections.split(',') if sections else []
    return generate_response('customers.customer_profile',params,'pdf',current,db)


@router.get('/commercial/quotes/{quote_id}/document.pdf')
def quotation_pdf(quote_id:UUID, lang:str='ar', current=Depends(get_current_user), db=Depends(get_db)):
    """The quotation document for the customer (commercial:quotes:read, within the caller's customer scope)."""
    from app.commercial.reporting.quotation.definitions import KEY
    return generate_response(KEY, dict(quote_id=str(quote_id), lang=lang), 'pdf', current, db)


@router.get('/reports/customers/lookups/{kind}')
def lookups(kind:str,q:str=Query('',max_length=120),current=Depends(get_current_user),db=Depends(get_db)):
    can=can_for(current)
    if not can(READ) or not any(can(p) for p in PERMISSIONS if not p.endswith('internal_audience')):
        raise HTTPException(403,'REPORT_PERMISSION_DENIED')
    query=scoped(db,current.tenant)
    if kind=='customers':
        return [dict(id=str(c.id),label=f'{c.customer_code} — {c.name}') for c in db.scalars(query.where(
            Customer.name.icontains(q,autoescape=True) | Customer.customer_code.icontains(q,autoescape=True)).limit(50))]
    if kind=='sales_owners':
        ids=db.scalars(query.with_only_columns(Customer.sales_owner_user_id).distinct()).all()
        return [dict(id=str(i),label=name) for i,name in providers.identity_factory(db,current.tenant).user_names(ids,q).items()]
    if kind=='products':
        if not can(DEMAND) or not providers.module_enabled(db,current.tenant,'production'):
            raise HTTPException(403,'SECTION_PERMISSION_DENIED')
        ids=db.scalars(query.with_only_columns(Customer.id)).all()
        products=sorted({d.product for d in providers.production_factory(db,current.tenant).demands(ids) if d.product and q.casefold() in d.product.casefold()})
        return [dict(id=p,label=p) for p in products[:50]]
    raise HTTPException(404,'LOOKUP_NOT_FOUND')
