from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select
from app.dependencies import get_db,get_current_tenant,require_permission
from app.core.authorization.scope_resolver import resolve_effective_scope
from app.core.interfaces.authorization_policy import AccessScope
from app.core.contact_records import SiteInput,save,view
from app.commercial.api.schemas import CustomerContactInput
from app.core.location_fields import normalize_city, assert_city_country
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
    def views(rows):
        result=[view(r) for r in rows]
        if kind=='sites':
            ids=[r['contact_id'] for r in result if r['contact_id']]
            names=dict(db.execute(select(CustomerContact.id,CustomerContact.name).where(
                CustomerContact.organization_id==tenant.organization_id,CustomerContact.customer_id==customer_id,
                CustomerContact.id.in_(ids))).all()) if ids else {}
            for row in result:row['contact_name']=names.get(row['contact_id'])
        return result
    if page is None:return views(db.scalars(query.limit(100)))
    params=PageParams(page=page)
    rows,total=paginate(db,query,params)
    return page_of(views(rows),total,params)


def write(db,tenant,customer_id,kind,payload,record_id=None):
    from pydantic import ValidationError
    customer = parent(db,tenant,customer_id,lock=True)
    m=model(kind)
    try:data=(CustomerContactInput if kind=='contacts' else SiteInput).model_validate(payload)
    except ValidationError as exc:
        if any(error['type']=='LOCATION_URL_INVALID' for error in exc.errors()):
            raise HTTPException(422,'LOCATION_URL_INVALID') from exc
        raise HTTPException(422,'DIRECTORY_DATA_INVALID') from exc
    if kind=='sites':
        previous=db.scalar(select(CustomerSite).where(CustomerSite.organization_id==tenant.organization_id,
            CustomerSite.customer_id==customer_id,CustomerSite.id==record_id)) if record_id else None
        values=data.model_dump()
        if 'country' not in payload:
            values['country']=previous.country if previous else customer.country
        try:
            values=normalize_city(values,previous)
            assert_city_country(db,tenant.organization_id,values,previous)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
        data=SiteInput.model_validate(values)
    if kind=='sites' and data.city:
        from app.core.interfaces.reference_lists import unknown_list_values
        previous=db.scalar(select(CustomerSite).where(CustomerSite.organization_id==tenant.organization_id,
            CustomerSite.customer_id==customer_id,CustomerSite.id==record_id)) if record_id else None
        if unknown_list_values(db,tenant.organization_id,'city',[data.city],[previous.city] if previous else []):
            raise HTTPException(422,'LIST_VALUE_UNKNOWN')
    if kind=='sites' and data.country:
        from app.core.interfaces.reference_lists import unknown_list_values
        if unknown_list_values(db,tenant.organization_id,'country',[data.country],[previous.country] if previous else []):
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
