"""Read-only audit inventory. Run from backend with PYTHONPATH=. No database writes."""
import ast
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
from app.main import app
from app.core.db import Base
from fastapi.routing import APIRoute

def policies(dep):
    result = []
    for attr in ('permission_policy', 'platform_permission'):
        if hasattr(dep.call, attr): result.append(getattr(dep.call, attr))
    for child in dep.dependencies: result.extend(policies(child))
    return result

imports, domains, api_persistence, app_api, sizes, table_access = [], [], [], [], [], []
hashes = {}
modules = {'commercial', 'foundation', 'production', 'quality', 'shipping', 'procurement', 'workforce', 'masterdata', 'platform', 'dashboard', 'core'}
for path in (ROOT / 'backend/app').rglob('*.py'):
    source = path.read_text(encoding='utf-8-sig')
    rel = path.relative_to(ROOT).as_posix()
    hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    tree = ast.parse(source)
    own = path.relative_to(ROOT / 'backend/app').parts[0]
    for n in ast.walk(tree):
        if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            sizes.append({'file': rel, 'line': n.lineno, 'name': n.name, 'lines': n.end_lineno - n.lineno + 1})
        if isinstance(n, ast.ImportFrom):
            target = n.module or ''
            record = {'file': rel, 'line': n.lineno, 'target': target}
            parts = target.split('.')
            if len(parts) > 1 and parts[0] == 'app' and parts[1] in modules and parts[1] != own:
                imports.append(record)
            if '/domain/' in rel and any(x in target for x in ('infrastructure', '.api', 'sqlalchemy', 'fastapi')): domains.append(record)
            if '/api/' in rel and '.infrastructure' in target: api_persistence.append(record)
            if '/application/' in rel and '.api' in target: app_api.append(record)
    for line, text in enumerate(source.splitlines(), 1):
        if 'metadata.tables' in text: table_access.append({'file': rel, 'line': line, 'code': text.strip()})
tables = []
for name, table in sorted(Base.metadata.tables.items()):
    tables.append({'name': name, 'tenant_column': 'organization_id' in table.c,
        'foreign_keys': [{'column': fk.parent.name, 'target': fk.target_fullname} for fk in table.foreign_keys],
        'indexes': [{'name': i.name, 'columns': [c.name for c in i.columns], 'unique': i.unique} for i in table.indexes],
        'constraints': [str(c) for c in table.constraints if c.__class__.__name__ in ('CheckConstraint', 'UniqueConstraint')]})
routes = [{'path': r.path, 'methods': sorted(r.methods), 'policies': policies(r.dependant),
           'source': r.endpoint.__module__ + '.' + r.endpoint.__name__} for r in app.routes if isinstance(r, APIRoute)]
result = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'source_hashes': hashes, 'routes': routes, 'tables': tables, 'cross_module_imports': imports,
          'domain_layer_imports': domains, 'api_persistence_imports': api_persistence, 'application_api_imports': app_api,
          'metadata_access': table_access, 'largest_symbols': sorted(sizes, key=lambda r: r['lines'], reverse=True)[:30]}
Path(__file__).with_name('inventory.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({'routes': len(routes), 'tables': len(tables), 'direct_tenant_tables': sum(t['tenant_column'] for t in tables),
                 'domain_layer_imports': domains, 'cross_module_imports': len(imports),
                 'api_persistence_imports': len(api_persistence), 'application_api_imports': len(app_api),
                 'metadata_accesses': len(table_access), 'largest_symbols': result['largest_symbols'][:6]}, indent=2))
