from uuid import UUID
from urllib.parse import quote
from fastapi import APIRouter, Depends, Response, Request, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_current_user, get_db, permission_checked_in_handler
from app.core.permission import has_permission
from app.core.reporting.service import ReportingService, definitions

router = APIRouter(prefix='/reports', tags=['reports'])
# Which report is asked for decides the permission: the service checks the definition's own code.
# Definitions list only the reports the user may run.
REPORT_PERMISSION = Depends(permission_checked_in_handler('reports:<definition.permission>'))

def can_for(current):
    return lambda code: current.user.is_organization_root or has_permission(current.auth_user, code)

@router.get('/definitions', dependencies=[REPORT_PERMISSION])
def get_definitions(request: Request, module: str | None = None, current=Depends(get_current_user), db: Session = Depends(get_db)):
    from types import SimpleNamespace
    from app.core.reporting.registry import registry
    fields = {f for d in registry.definitions.values() for f in d.context_fields}
    values = {}
    for field in fields:
        value = request.query_params.get(field)
        try:
            values[field] = UUID(value) if value and field.endswith('_id') else value
        except ValueError:
            raise HTTPException(422, 'INVALID_REPORT_PARAMS')
    values['audience'] = request.query_params.get('audience', 'internal')
    return definitions(db, current.tenant, can_for(current), module, SimpleNamespace(**values))

def generate_response(key, payload, fmt, current, db):
    content, filename = ReportingService(db, current.tenant, can_for(current), current.user.full_name).generate(key, payload, fmt)
    headers = {'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'}
    if fmt == 'pdf':
        headers['Content-Disposition'] = f"attachment; filename=\"report.pdf\"; filename*=UTF-8''{quote(filename)}"
        headers['Access-Control-Expose-Headers'] = 'Content-Disposition'
    else:
        headers['Content-Security-Policy'] = "default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
    return Response(content, media_type='application/pdf' if fmt == 'pdf' else 'text/html', headers=headers)

@router.post('/{report_key}/preview', dependencies=[REPORT_PERMISSION])
def preview(report_key: str, payload: dict, current=Depends(get_current_user), db: Session = Depends(get_db)):
    return generate_response(report_key, payload, 'html', current, db)

@router.post('/{report_key}/pdf', dependencies=[REPORT_PERMISSION])
def pdf(report_key: str, payload: dict, current=Depends(get_current_user), db: Session = Depends(get_db)):
    return generate_response(report_key, payload, 'pdf', current, db)
