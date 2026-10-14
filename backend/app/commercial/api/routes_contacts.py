from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select
from app.dependencies import get_db,get_current_tenant,require_permission
from app.core.authorization.scope_resolver import resolve_effective_scope
from app.core.interfaces.authorization_policy import AccessScope
from app.core.contact_records import ContactInput,SiteInput,save,view
from app.core.pagination import PageParams,paginate,page_of
from app.commercial.infrastructure.models import Customer
from app.commercial.infrastructure.contact_models import CustomerContact,CustomerSite

router=APIRouter(prefix='/commercial/customers/{customer_id}',tags=['customer-directory'],dependencies=[Depends(require_permission('commercial:customers:read'))])


def parent(db,tenant,cid,lock=False):
    q=select(Customer).where(Customer.organization_id==tenant.organization_id,Customer.id==cid)
    scope=resolve_effective_scope(db,tenant.user_id,tenant.organization_id,'commercial:customers:read',tenant.is_organization_root)
    if scope!=AccessScope.ORGANIZATION:q=q.where(Customer.sales_owner_user_id==tenant.user_id)
    if lock:
        write_scope=resolve_effective_scope(db,tenant.user_id,tenant.organization_id,'commercial:customers:update',tenant.is_organization_root)
        if write_scope!=AccessScope.ORGANIZATION:q=q.where(Customer.sales_owner_user_id==tenant.user_id)
    row=db.scalar(q.with_for_update() if lock else q)
    if not row:raise HTTPException(404,'CUSTOMER_NOT_FOUND')
    return row


def model(kind):
    if kind not in ('contacts','sites'):raise HTTPException(404,'DIRECTORY_UNKNOWN')
    return CustomerContact if kind=='contacts' else CustomerSite


@router.get('/directory/{kind}')
def listing(customer_id:UUID,kind:str,search:str=Query('',max_length=120),page:int|None=Query(None,ge=1),db=Depends(get_db),tenant=Depends(get_current_tenant)):
    parent(db,tenant,customer_id)
    m=model(kind)
    query=select(m).where(m.organization_id==tenant.organization_id,m.customer_id==customer_id,
        m.name.icontains(search,autoescape=True)).order_by(m.is_default.desc(),m.name,m.id)
    if page is None:return [view(r) for r in db.scalars(query.limit(100))]
    params=PageParams(page=page)
    rows,total=paginate(db,query,params)
    return page_of([view(r) for r in rows],total,params)


def write(db,tenant,customer_id,kind,payload,record_id=None):
    from pydantic import ValidationError
    parent(db,tenant,customer_id,lock=True)
    m=model(kind)
    try:data=(ContactInput if kind=='contacts' else SiteInput).model_validate(payload)
    except ValidationError:raise HTTPException(422,'DIRECTORY_DATA_INVALID')
    if kind=='sites' and data.city:
        from app.core.interfaces.reference_lists import unknown_list_values
        previous=db.scalar(select(CustomerSite).where(CustomerSite.organization_id==tenant.organization_id,
            CustomerSite.customer_id==customer_id,CustomerSite.id==record_id)) if record_id else None
        if unknown_list_values(db,tenant.organization_id,'city',[data.city],[previous.city] if previous else []):
            raise HTTPException(422,'LIST_VALUE_UNKNOWN')
    if kind=='sites' and data.contact_id:
        if not db.scalar(select(CustomerContact.id).where(CustomerContact.organization_id==tenant.organization_id,
            CustomerContact.customer_id==customer_id,CustomerContact.id==data.contact_id,CustomerContact.active.is_(True))):
            raise HTTPException(422,'CONTACT_NOT_IN_CUSTOMER')
    return save(db,tenant,m,'customer_id',customer_id,data,record_id)


@router.post('/directory/{kind}',status_code=201,dependencies=[Depends(require_permission('commercial:customers:update'))])
def create(customer_id:UUID,kind:str,payload:dict,db=Depends(get_db),tenant=Depends(get_current_tenant)):
    return write(db,tenant,customer_id,kind,payload)


@router.put('/directory/{kind}/{record_id}',dependencies=[Depends(require_permission('commercial:customers:update'))])
def update(customer_id:UUID,kind:str,record_id:UUID,payload:dict,db=Depends(get_db),tenant=Depends(get_current_tenant)):
    return write(db,tenant,customer_id,kind,payload,record_id)
