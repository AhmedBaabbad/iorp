"""Shared order response helpers for the production order and planning routes."""
from fastapi import Depends, HTTPException
from app.core.permission import has_permission
from app.dependencies import CurrentUserContext, get_current_user
from app.production.application.order_status_service import OrderStatusService
from app.production.application.planning_order_service import order_response


def permission_check(current: CurrentUserContext = Depends(get_current_user)):
    """Per-action permission test for the status service; mirrors require_permission (root sees all)."""
    return lambda code: current.user.is_organization_root or has_permission(current.auth_user, code)


def with_lifecycle(order, db, tenant, customers, can):
    """Order detail plus its lifecycle: status version, actual dates, late flags and allowed actions."""
    result = order_response(order, db, tenant, customers)
    result["lifecycle"] = OrderStatusService(db, tenant).describe(order, can)
    return result


def lifecycle_errors(exc):
    return HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail})
