from uuid import UUID
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select
from app.dependencies import get_db, get_current_tenant, require_permission, require_any_permission, permission_check
from app.core.pagination import page_params
from app.core import files
from app.core.storage import LocalFileStorage
from app.core.interfaces.product_catalog import sample_products
from app.commercial.api.complaint_schemas import ComplaintCreate, Assignment, Investigation, Items, Resolution, Transition, Note, Communication, LinkInput
from app.commercial.application.complaint_service import ComplaintService, fail
from app.commercial.domain.complaints import PREFIX, ACTIONS
from app.commercial.infrastructure.complaint_models import ComplaintAttachment
from app.commercial.infrastructure.models import Customer
from app.commercial.infrastructure.complaint_queries import eligible_users, reference_query, table, LINKS

router=APIRouter(prefix='/complaints',tags=['commercial-complaints'],dependencies=[Depends(require_permission(PREFIX+'read'))])

def service(db=Depends(get_db),tenant=Depends(get_current_tenant)):
    return ComplaintService(db,tenant)

def execute(s,can,fn):
    try:
        return s.view(fn(),can)
    except Exception:
        s.db.rollback()
        raise

@router.get('')
def listing(search:str=Query('',max_length=120),status:str|None=None,customer_id:UUID|None=None,department:str|None=None,overdue:bool=False,
            params=Depends(page_params),s=Depends(service),can=Depends(permission_check)):
    return s.list(params,can,search=search,status=status,customer_id=customer_id,department=department,overdue=overdue)

@router.get('/customers')
def customers(search:str=Query('',max_length=120),id:UUID|None=None,s=Depends(service)):
    q=s.customers()
    q=q.where(Customer.id==id) if id else q.where(Customer.name.icontains(search,autoescape=True))
    return [dict(id=c.id,name=c.name) for c in s.db.scalars(q.order_by(Customer.name,Customer.id).limit(30))]

@router.get('/summary')
def summary(customer_id:UUID|None=None,department:str|None=None,s=Depends(service)):
    return s.summary(customer_id=customer_id,department=department)

@router.get('/products')
def catalogue(s=Depends(service)):
    return [dict(key=p.key,name_ar=p.name_ar,name_en=p.name_en,default_unit=p.default_unit,
        properties=[dict(key=x.key,name_ar=x.name_ar,name_en=x.name_en,unit=x.unit,kind=x.kind,options=x.options) for x in p.properties]) for p in sample_products(s.db,s.org) if p.active]

# A customer's sales order lines and samples a complaint line can take its agreed specification from (copied when chosen).
@router.get('/sources')
def sources(customer_id:UUID,search:str=Query('',max_length=120),s=Depends(service),can=Depends(permission_check)):
    return s.sources(customer_id,can,search)

@router.post('',status_code=201,dependencies=[Depends(require_permission(PREFIX+'create'))])
def create(data:ComplaintCreate,s=Depends(service),can=Depends(permission_check)):
    return execute(s,can,lambda:s.create(data,can))

@router.get('/{cid}')
def detail(cid:UUID,s=Depends(service),can=Depends(permission_check)):
    return s.view(s.get(cid),can)

@router.get('/{cid}/assignees',dependencies=[Depends(require_permission(PREFIX+'assign'))])
def assignees(cid:UUID,search:str=Query('',max_length=100),s=Depends(service)):
    row=s.get(cid)
    return eligible_users(s.db,s.tenant,s.customer(row.customer_id),search)

@router.get('/{cid}/references')
def references(cid:UUID,kind:str,search:str=Query('',max_length=120),s=Depends(service),can=Depends(permission_check)):
    row=s.get(cid)
    if kind not in LINKS: fail('REFERENCE_KIND_INVALID',422)
    if not s.reference_allowed(row.customer_id,kind,can): fail('REFERENCE_PERMISSION_REQUIRED',403)
    t=table(LINKS[kind][0]); label=t.c[LINKS[kind][1]]
    return [dict(id=r['id'],label=r[LINKS[kind][1]]) for r in s.db.execute(reference_query(s.org,row.customer_id,kind).where(label.icontains(search,autoescape=True)).order_by(label,t.c.id).limit(30)).mappings()]

@router.post('/{cid}/assign',dependencies=[Depends(require_permission(PREFIX+'assign'))])
def assign(cid:UUID,data:Assignment,s=Depends(service),can=Depends(permission_check)):
    return execute(s,can,lambda:s.change(cid,data,'assign',can))

@router.post('/{cid}/investigate',dependencies=[Depends(require_permission(PREFIX+'investigate'))])
def investigate(cid:UUID,data:Investigation,s=Depends(service),can=Depends(permission_check)):
    return execute(s,can,lambda:s.change(cid,data,'investigate',can))

@router.post('/{cid}/refer-quality',dependencies=[Depends(require_permission(PREFIX+'investigate')),Depends(require_permission('quality:ncr_reports:create'))])
def refer_quality(cid:UUID,data:Note,s=Depends(service),can=Depends(permission_check)):
    return execute(s,can,lambda:s.refer_quality(cid,data))

@router.post('/{cid}/resolve',dependencies=[Depends(require_permission(PREFIX+'resolve'))])
def resolve(cid:UUID,data:Resolution,s=Depends(service),can=Depends(permission_check)):
    return execute(s,can,lambda:s.change(cid,data,'resolve',can))

@router.put('/{cid}/items',dependencies=[Depends(require_permission(PREFIX+'update'))])
def items(cid:UUID,data:Items,s=Depends(service),can=Depends(permission_check)):
    """Edit the complaint's product lines while it is open; measurements already recorded on a kept line stay."""
    return execute(s,can,lambda:s.update_items(cid,data,can))

# One record of contact: an internal follow-up, or (to_customer) what was sent to the customer.
@router.post('/{cid}/communications',dependencies=[Depends(require_permission(PREFIX+'update'))])
def communicate(cid:UUID,data:Communication,s=Depends(service),can=Depends(permission_check)):
    return execute(s,can,lambda:s.change(cid,data,'response' if data.to_customer else 'note',can))

@router.post('/{cid}/links',dependencies=[Depends(require_permission(PREFIX+'update'))])
def link(cid:UUID,data:LinkInput,s=Depends(service),can=Depends(permission_check)):
    return execute(s,can,lambda:s.link(cid,data,can))

@router.post('/{cid}/transitions',dependencies=[Depends(require_any_permission([PREFIX+p for _,_,p in ACTIONS.values()]))])
def transition(cid:UUID,data:Transition,s=Depends(service),can=Depends(permission_check)):
    return execute(s,can,lambda:s.change(cid,data,'transition',can))

@router.post('/{cid}/attachments',dependencies=[Depends(require_permission(PREFIX+'update'))])
async def attachment(cid:UUID,version:int=Form(...),file:UploadFile=File(...),s=Depends(service),can=Depends(permission_check)):
    content=await file.read(files.read_limit('attachment'))
    return execute(s,can,lambda:s.attach(cid,version,file.filename,content))  # a refused file: 422 FILE_<code>

@router.get('/{cid}/attachments/{attachment_id}')
def download(cid:UUID,attachment_id:UUID,s=Depends(service)):
    s.get(cid)
    a=s.db.scalar(select(ComplaintAttachment).where(ComplaintAttachment.organization_id==s.org,ComplaintAttachment.complaint_id==cid,ComplaintAttachment.id==attachment_id))
    if not a: fail('ATTACHMENT_NOT_FOUND',404)
    path=LocalFileStorage().resolve(a.storage_path)
    if not path.is_file(): fail('ATTACHMENT_NOT_FOUND',404)
    return FileResponse(path,filename=a.filename,media_type=a.content_type)
