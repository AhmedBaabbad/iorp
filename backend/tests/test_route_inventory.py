import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.main import app
from tests.route_inventory import dependency_calls, discover_routes, require_nonempty, validate_registered


def test_real_application_inventory_is_not_empty():
    routes = discover_routes(app)
    assert len(routes) >= 450
    assert any(r.path == '/api/v1/auth/me/email-change' for r in routes)
    assert any(r.path.startswith('/api/v1/production/') for r in routes)


def test_incomplete_application_fails_closed():
    with pytest.raises(RuntimeError, match='Incomplete security inventory'):
        discover_routes(FastAPI())


def test_empty_parameterized_cases_fail_instead_of_skipping():
    with pytest.raises(RuntimeError, match='No security test cases'):
        require_nonempty([], 'permissions')


def test_nested_prefixes_and_include_dependencies_match_real_http():
    miniature = FastAPI()
    router = APIRouter()
    outer = APIRouter()
    calls = []
    def permission():
        calls.append('checked')
    @router.get('/record')
    def record():
        return {'ok': True}
    outer.include_router(router, prefix='/inner', dependencies=[Depends(permission)])
    miniature.include_router(outer, prefix='/outer')
    routes = discover_routes(miniature, minimum=1)
    assert routes[0].path == '/outer/inner/record'
    assert permission in list(dependency_calls(routes[0].dependant))
    with TestClient(miniature) as client:
        assert client.get(routes[0].path).status_code == 200
    assert calls == ['checked']


def test_new_route_is_discovered_even_after_schema_was_cached():
    miniature = FastAPI()
    miniature.openapi()
    @miniature.get('/new')
    def new():
        return {}
    assert [r.path for r in discover_routes(miniature, minimum=1)] == ['/new']


def test_application_routes_match_review_inventory():
    import json
    from pathlib import Path
    registered = json.loads((Path(__file__).parent / 'route_inventory_registry.json').read_text(encoding='utf-8'))
    validate_registered(discover_routes(app), registered)


def test_new_unregistered_endpoint_requires_review():
    miniature = FastAPI()
    @miniature.get('/unregistered')
    def unregistered():
        return {}
    with pytest.raises(RuntimeError, match='Route registration review required'):
        validate_registered(discover_routes(miniature, minimum=1), {})
