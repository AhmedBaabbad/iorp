from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select, or_, case
from sqlalchemy.exc import IntegrityError
from app.dependencies import get_db, get_current_tenant, require_permission, require_any_permission
from app.core.pagination import page_params, paginate, page_of
from app.core.interfaces.workforce_directory import directory as workforce
from app.shipping.application.directory_service import MODELS, validate, view, duplicate_identity, identity_conflict

router = APIRouter(prefix='/shipping/directory', tags=['transport-directory'])
READ = 'shipping:directory:read'
WRITE = 'shipping:directory:write'
QUICK = ['shipping:shipments:create', 'shipping:shipments:update', 'procurement:receipts:create', 'procurement:receipts:update']
USE = [READ, WRITE, *QUICK, 'shipping:shipments:reschedule']


class CarrierInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=30)
    active: bool = True
    version: int | None = Field(None, ge=1)


class DriverInput(CarrierInput):
    name: str | None = Field(None, max_length=200)
    affiliation: Literal['internal', 'external']
    workforce_member_id: UUID | None = None
    identity_no: str | None = Field(None, max_length=40)
    carrier_id: UUID | None = None
    email: str | None = Field(None, max_length=255)
    license_no: str | None = Field(None, max_length=40)
    license_expiry: date | None = None
    default_vehicle_id: UUID | None = None
    vehicle_type: str | None = Field(None, max_length=80)
    notes: str | None = None


class QuickDriverInput(DriverInput):
    affiliation: Literal['external'] = 'external'


class VehicleInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    plate: str = Field(min_length=1, max_length=40)
    vehicle_type: str | None = Field(None, max_length=80)
    carrier_id: UUID | None = None
    active: bool = True
    version: int | None = Field(None, ge=1)


SCHEMAS = {'drivers': DriverInput, 'vehicles': VehicleInput, 'carriers': CarrierInput}


def model_for(kind):
    if kind not in MODELS:
        raise HTTPException(404, 'DIRECTORY_UNKNOWN')
    return MODELS[kind]


@router.get('/workers', dependencies=[Depends(require_permission(WRITE))])
def workers(search: str = Query('', max_length=120), db=Depends(get_db), tenant=Depends(get_current_tenant)):
    return workforce().members(db, tenant.organization_id, search)


@router.get('/customers/{customer_id}/{kind}', dependencies=[Depends(require_any_permission(['shipping:shipments:create', 'shipping:shipments:update']))])
def customer_options(customer_id: UUID, kind: str, search: str = Query('', max_length=120), db=Depends(get_db), tenant=Depends(get_current_tenant)):
    from app.core.interfaces.customer_delivery import directory
    return directory().options(db, tenant.organization_id, customer_id, kind, search)


def search_match(db, org, kind, model, search):
    match = model.name.icontains(search, autoescape=True)
    if kind == 'vehicles':
        match = or_(match, model.plate.icontains(search, autoescape=True))
    return match


def driver_views(db, org, search='', active_only=False):
    from app.core.phones import phone_search_terms
    terms = {term.casefold() for term in phone_search_terms(search)}
    m = MODELS['drivers']
    query = select(m).where(m.organization_id == org)
    if active_only:query = query.where(m.active.is_(True))
    rows = list(db.scalars(query))
    members = workforce().batch(db, org, {r.workforce_member_id for r in rows if r.affiliation == 'internal'})
    result = []
    for row in rows:
        if active_only and row.affiliation == 'internal' and not members.get(row.workforce_member_id, {}).get('active'):
            continue
        item = view(db, org, row, members)
        if not any(term in ' '.join(str(item.get(k) or '') for k in ('name','phone','identity_no')).casefold() for term in terms):continue
        result.append(item)
    return sorted(result, key=lambda r: (r['name'].casefold(), str(r['id'])))


@router.get('/{kind}/options', dependencies=[Depends(require_any_permission(USE))])
def options(kind: str, search: str = Query('', max_length=120), selected_id: UUID | None = None, db=Depends(get_db), tenant=Depends(get_current_tenant)):
    m = model_for(kind)
    if kind == 'drivers':
        rows = driver_views(db, tenant.organization_id, search, active_only=True)
        if selected_id and not any(r['id'] == selected_id for r in rows):
            selected = db.scalar(select(m).where(m.organization_id == tenant.organization_id, m.id == selected_id, m.active.is_(True)))
            if selected:
                members = workforce().batch(db, tenant.organization_id, [selected.workforce_member_id]) if selected.affiliation == 'internal' else {}
                if selected.affiliation != 'internal' or members.get(selected.workforce_member_id, {}).get('active'):
                    rows.append(view(db, tenant.organization_id, selected, members))
        rows.sort(key=lambda row: row['id'] != selected_id)
        return [{key:row[key] for key in ('id','name','affiliation','default_vehicle_id','license_expiry')} for row in rows[:50]]
    rows = db.scalars(select(m).where(m.organization_id == tenant.organization_id, m.active.is_(True),
        or_(search_match(db, tenant.organization_id, kind, m, search), m.id == selected_id)).order_by(case((m.id == selected_id, 0), else_=1), m.name, m.id).limit(50))
    result = []
    for row in rows:
        item = view(db, tenant.organization_id, row)
        fields = ['plate'] if kind == 'vehicles' else []
        result.append(dict(id=row.id, name=item['name'], **{field: item[field] for field in fields}))
    return result


@router.get('/{kind}', dependencies=[Depends(require_permission(READ))])
def listing(kind: str, search: str = Query('', max_length=120), params=Depends(page_params), db=Depends(get_db), tenant=Depends(get_current_tenant)):
    m = model_for(kind)
    if kind == 'drivers':
        rows = driver_views(db, tenant.organization_id, search)
        return page_of(rows[params.offset:params.offset+params.page_size], len(rows), params)
    rows, total = paginate(db, select(m).where(m.organization_id == tenant.organization_id,
        search_match(db, tenant.organization_id, kind, m, search)).order_by(m.name, m.id), params)
    return page_of([view(db, tenant.organization_id, row) for row in rows], total, params)


def save(kind, payload, db, tenant, record_id=None, schema=None):
    m = model_for(kind)
    payload = dict(payload)
    if kind == 'drivers' and payload.get('affiliation') == 'internal' and schema is not QuickDriverInput:
        for field in ('name', 'phone', 'email', 'identity_no'):
            payload.pop(field, None)
    try:
        data = (schema or SCHEMAS[kind]).model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(422, 'DIRECTORY_DATA_INVALID') from exc
    values = data.model_dump(exclude={'version'})
    row = None
    if record_id:
        row = db.scalar(select(m).where(m.organization_id == tenant.organization_id, m.id == record_id)
                        .with_for_update().execution_options(populate_existing=True))
        if not row:
            raise HTTPException(404, 'DIRECTORY_RECORD_NOT_FOUND')
        if data.version != row.version:
            raise HTTPException(409, 'DIRECTORY_CHANGED')
    values = validate(db, tenant.organization_id, kind, values, row)
    identity = values.get('identity_no')
    label = values['name']
    # Internal personal data remains workforce-owned. Read it live, never store a second employee record.
    if kind == 'drivers' and values['affiliation'] == 'internal':
        values.update(name='', phone=None, email=None, identity_no=None)
    if row:
        for key, value in values.items():
            setattr(row, key, value)
        row.version += 1
        row.updated_by = tenant.user_id
    else:
        row = m(**values, organization_id=tenant.organization_id, created_by=tenant.user_id, updated_by=tenant.user_id)
        db.add(row)
    from app.core.interfaces.audit_trail import record
    try:
        db.flush()
        record(db, tenant.organization_id, 'directory.update' if record_id else 'directory.create', row.__tablename__,
               row.id, label, tenant.user_id, {'version': row.version, 'active': row.active})
        db.commit()
    except IntegrityError:
        db.rollback()
        if kind == 'drivers':
            existing = duplicate_identity(db, tenant.organization_id, identity, record_id)
            if existing:
                identity_conflict(existing)
        raise HTTPException(409, 'DIRECTORY_DUPLICATE')
    return view(db, tenant.organization_id, row)


@router.post('/drivers/quick', status_code=201, dependencies=[Depends(require_any_permission(QUICK))])
def quick_driver(payload: dict, db=Depends(get_db), tenant=Depends(get_current_tenant)):
    return save('drivers', payload, db, tenant, schema=QuickDriverInput)


@router.post('/{kind}', status_code=201, dependencies=[Depends(require_permission(WRITE))])
def create(kind: str, payload: dict, db=Depends(get_db), tenant=Depends(get_current_tenant)):
    return save(kind, payload, db, tenant)


@router.put('/{kind}/{record_id}', dependencies=[Depends(require_permission(WRITE))])
def update(kind: str, record_id: UUID, payload: dict, db=Depends(get_db), tenant=Depends(get_current_tenant)):
    return save(kind, payload, db, tenant, record_id)
