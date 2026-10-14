from uuid import UUID
from fastapi import APIRouter,Depends,Query,HTTPException
from sqlalchemy import select
from app.dependencies import get_db,get_current_tenant,require_permission,require_any_permission
from app.core.contact_records import ContactInput,save,view
from app.core.pagination import PageParams,paginate,page_of
from app.procurement.infrastructure.contact_models import SupplierContact
from app.procurement.infrastructure.models import Supplier

router=APIRouter(prefix='/procurement/suppliers/{supplier_id}/contacts',tags=['supplier-contacts'])


def parent(db,tenant,supplier_id,lock=False):
    query=select(Supplier).where(Supplier.id==supplier_id,Supplier.organization_id==tenant.organization_id)
    row=db.scalar(query.with_for_update() if lock else query)
    if row is None:raise HTTPException(404,'SUPPLIER_NOT_FOUND')
    return row


@router.get('',dependencies=[Depends(require_any_permission(['procurement:suppliers:read','procurement:purchase_orders:create','procurement:purchase_orders:update']))])
def listing(supplier_id:UUID,search:str=Query('',max_length=120),page:int|None=Query(None,ge=1),db=Depends(get_db),tenant=Depends(get_current_tenant)):
    parent(db,tenant,supplier_id)
    query=select(SupplierContact).where(SupplierContact.organization_id==tenant.organization_id,
        SupplierContact.supplier_id==supplier_id,SupplierContact.name.icontains(search,autoescape=True)).order_by(SupplierContact.is_default.desc(),SupplierContact.name,SupplierContact.id)
    if page is None:return [view(r) for r in db.scalars(query.limit(100))]
    params=PageParams(page=page)
    rows,total=paginate(db,query,params)
    return page_of([view(r) for r in rows],total,params)


@router.post('',status_code=201,dependencies=[Depends(require_permission('procurement:suppliers:update'))])
def create(supplier_id:UUID,data:ContactInput,db=Depends(get_db),tenant=Depends(get_current_tenant)):
    parent(db,tenant,supplier_id,lock=True)
    return save(db,tenant,SupplierContact,'supplier_id',supplier_id,data)


@router.put('/{record_id}',dependencies=[Depends(require_permission('procurement:suppliers:update'))])
def update(supplier_id:UUID,record_id:UUID,data:ContactInput,db=Depends(get_db),tenant=Depends(get_current_tenant)):
    parent(db,tenant,supplier_id,lock=True)
    return save(db,tenant,SupplierContact,'supplier_id',supplier_id,data,record_id)
