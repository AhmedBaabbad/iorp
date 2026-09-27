from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import CurrentUserContext, get_db, require_permission
from app.foundation.api.schemas import PermissionCatalogItemResponse, PermissionCatalogResponse, PermissionModuleResponse
from app.foundation.application.services import FoundationService
from app.foundation.domain.permission_catalog import MODULE_NAMES, PERMISSION_BY_CODE

router = APIRouter(tags=["foundation-permissions"])


@router.get("/permissions", response_model=PermissionCatalogResponse)
def list_permissions(
    current: CurrentUserContext = Depends(require_permission("foundation:permissions:read")),
    db: Session = Depends(get_db),
) -> PermissionCatalogResponse:
    service = FoundationService(db)
    grouped: dict[str, list[PermissionCatalogItemResponse]] = {}
    permissions = service.list_permissions_for_organization(current.tenant.organization_id)
    for permission in permissions:
        definition = PERMISSION_BY_CODE.get(permission.code)
        grouped.setdefault(permission.module_name, []).append(PermissionCatalogItemResponse(
            id=permission.id, code=permission.code, module=permission.module_name,
            resource=permission.resource_name, action=permission.action_name,
            name=permission.name, description=permission.description,
            name_en=definition.name_en if definition else permission.name,
            name_ar=definition.name_ar if definition else permission.name,
            description_en=definition.description_en if definition else permission.description,
            description_ar=definition.description_ar if definition else permission.description,
            scopable=definition.scopable if definition else False,
            owner_field=definition.owner_field if definition else None,
        ))
    modules = [PermissionModuleResponse(
        module=module,
        module_name_en=MODULE_NAMES.get(module, {}).get("en", module),
        module_name_ar=MODULE_NAMES.get(module, {}).get("ar", module),
        permissions=items,
    ) for module, items in sorted(grouped.items())]
    return PermissionCatalogResponse(total=len(permissions), modules=modules)
