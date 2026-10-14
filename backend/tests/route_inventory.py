"""Fail-closed HTTP route discovery for security tests across FastAPI versions.

FastAPI 0.143 includes routers lazily. Its effective candidates carry the full
prefix and inherited dependencies; walking original_router loses that context.
This adapter is test-only and never changes the application's routing objects.
"""
from copy import copy

from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from starlette.routing import Mount

MIN_APPLICATION_ROUTES = 450


def discover_routes(application, *, minimum=MIN_APPLICATION_ROUTES):
    found = []

    def visit(entries):
        for entry in entries:
            if isinstance(entry, APIRoute):
                found.append(entry)
            elif callable(getattr(entry, 'effective_candidates', None)):
                visit(entry.effective_candidates())
            elif isinstance(getattr(entry, 'original_route', None), APIRoute):
                # Materialize a test view, retaining effective dependency context.
                route = copy(entry.original_route)
                for name in ('path', 'path_format', 'methods', 'dependant', 'include_in_schema'):
                    setattr(route, name, getattr(entry, name))
                found.append(route)
            elif isinstance(entry, Mount):
                raise RuntimeError('Mounted applications require explicit security inventory support')
            elif hasattr(entry, 'original_router'):
                raise RuntimeError('Unsupported lazy router representation')

    visit(application.routes)
    if len(found) < minimum:
        raise RuntimeError(f'Incomplete security inventory: {len(found)} routes; minimum {minimum}')
    schema = get_openapi(title=application.title, version=application.version, routes=application.routes)
    operations = {(path, method.upper()) for path, item in schema.get('paths', {}).items()
                  for method in item if method in {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'}}
    discovered = {(r.path_format, method) for r in found if r.include_in_schema for method in r.methods}
    if operations != discovered:
        raise RuntimeError(f'Security inventory disagrees with OpenAPI: {sorted(operations ^ discovered)}')
    return found


def dependency_calls(dependency):
    yield dependency.call
    for child in dependency.dependencies:
        yield from dependency_calls(child)


def require_nonempty(cases, label):
    cases = list(cases)
    if not cases:
        raise RuntimeError(f'No security test cases discovered: {label}')
    return cases


def validate_registered(routes, registered):
    actual = {f'{method} {route.path}' for route in routes for method in route.methods}
    expected = set(registered)
    if actual != expected:
        raise RuntimeError(f'Route registration review required: added={sorted(actual - expected)}, removed={sorted(expected - actual)}')
