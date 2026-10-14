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
def quotation_pdf(quote_id:UUID, lang:str|None=Query(None, pattern='^(ar|en)$'), current=Depends(get_current_user), db=Depends(get_db)):
    """The quotation document for the customer (commercial:quotes:read, within the caller's customer scope), in the
    language chosen in the quotation settings unless one is asked for."""
    from app.commercial.application.quote_settings_service import QuoteSettingsService
    from app.commercial.reporting.quotation.definitions import KEY
    from app.commercial.application.visibility import QUOTES_READ, visible_owner
    from app.commercial.infrastructure.repositories import QuoteRepository
    quotes = QuoteRepository(db)
    quotes.owner_user_id = visible_owner(db, current.tenant, QUOTES_READ)
    if quotes.get_by_id(current.tenant.organization_id, quote_id) is None:
        raise HTTPException(404, 'Quote not found.')  # RBAC-002: not one of the user's customers
    lang = lang or QuoteSettingsService(db, current.tenant.organization_id).language()
    return generate_response(KEY, dict(quote_id=str(quote_id), lang=lang), 'pdf', current, db)


@router.get('/reports/customers/lookups/{kind}')
def lookups(kind:str,q:str=Query('',max_length=120),current=Depends(get_current_user),db=Depends(get_db)):
    can=can_for(current)
    if kind in ('complaints','complaint_customers'):
        if not can('commercial:complaints:read') or not can('commercial:complaints:report'):
            raise HTTPException(403,'REPORT_PERMISSION_DENIED')
        from app.commercial.application.complaint_service import ComplaintService
        service=ComplaintService(db,current.tenant)
        if kind=='complaints':
            return [dict(id=str(c.id),label=f'{c.number} — {c.title}') for c in db.scalars(service.filtered(search=q).limit(50))]
        return [dict(id=str(c.id),label=c.name) for c in db.scalars(service.customers().where(Customer.name.icontains(q,autoescape=True)).order_by(Customer.name,Customer.id).limit(50))]
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
    if kind=='sample_products':
        if not can('commercial:samples:read'):
            raise HTTPException(403,'SECTION_PERMISSION_DENIED')
        from app.commercial.infrastructure.models import Sample
        from app.core.interfaces.product_catalog import products as catalog_products
        from .queries import bounded, LIMIT
        keys=bounded(db.scalars(select(Sample.product_type).where(Sample.customer_id.in_(query.with_only_columns(Customer.id)))
            .distinct().order_by(Sample.product_type).limit(LIMIT + 1)))
        definitions=catalog_products(db,current.tenant.organization_id,keys)
        rows=[dict(id=k,label=(definitions[k].name_ar+' / '+definitions[k].name_en) if k in definitions else k) for k in keys]
        return [r for r in rows if q.casefold() in (r['label']+' '+r['id']).casefold()][:50]
    raise HTTPException(404,'LOOKUP_NOT_FOUND')
