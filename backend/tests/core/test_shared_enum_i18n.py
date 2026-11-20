import ast
import importlib
import json
import re
from enum import Enum
from pathlib import Path

import pytest

from app.core.enum_i18n import enum_catalog, enum_label, shared_root


def domain_values():
    """Discover enum classes and semantic domain collections, never a copied value list."""
    app = Path(__file__).resolve().parents[2] / 'app'
    semantic = re.compile(r'(STATUS|STATUSES|REASONS|CATEGORIES|TYPES|KINDS|PRIORITIES|METHODS|DISPOSITIONS|RESULTS|SEVERITIES)$')
    files = list(app.glob('*/domain/*.py')) + list((app / 'core/interfaces').glob('*.py'))
    for file in sorted(files):
        tree = ast.parse(file.read_text(encoding='utf-8-sig'))
        names = [n.name for n in tree.body if isinstance(n, ast.ClassDef) and any('Enum' in ast.unparse(b) for b in n.bases)]
        names += [t.id for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                  for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
                  if isinstance(t, ast.Name) and t.id.isupper() and semantic.search(t.id)]
        if not names:
            continue
        module = importlib.import_module('app.' + '.'.join(file.relative_to(app).with_suffix('').parts))
        for name in names:
            obj = getattr(module, name)
            values = [v.value for v in obj] if isinstance(obj, type) and issubclass(obj, Enum) else list(obj) if isinstance(obj, (dict, set, frozenset, list, tuple)) else []
            for value in values:
                if isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_]*', value):
                    owner = file.parts[-3]
                    if owner == 'core':
                        owner = 'notifications' if file.stem == 'notifications' else 'foundation'
                    yield owner, name, value


def test_every_domain_enum_has_shared_translations():
    fields = json.loads((shared_root() / 'domain-fields.json').read_text())
    for locale in ('ar', 'en'):
        catalog = enum_catalog(locale)
        missing = []
        for module, source, value in domain_values():
            target = fields.get(module + '.' + source)
            if not target:
                missing.append((module, source, value))
                continue
            group, field = target.split('.')
            if value not in catalog.get(group, {}).get(field, {}):
                missing.append((module, source, value))
        assert not missing, missing


def test_shared_locales_are_aligned():
    def leaves(data, prefix=''):
        return {prefix} if isinstance(data, str) else set().union(*(leaves(v, prefix + '.' + k) for k, v in data.items()))
    assert leaves(enum_catalog('ar')) == leaves(enum_catalog('en'))
    aliases = json.loads((shared_root() / 'aliases.json').read_text())
    for target in aliases.values():
        value = enum_catalog('ar')
        for part in target.split('.'):
            value = value[part]
        assert value


def test_reader_missing_translation_is_explicit(monkeypatch, caplog):
    assert enum_label('shipping', 'status', 'draft', 'en') == 'Draft'
    monkeypatch.setenv('APP_ENV', 'test')
    with pytest.raises(ValueError, match='Missing enum translation'):
        enum_label('shipping', 'status', 'unknown', 'ar')
    monkeypatch.setenv('APP_ENV', 'production')
    assert enum_label('shipping', 'status', 'unknown', 'ar') == '—'
    assert 'Missing enum translation' in caplog.text
    assert 'unknown' not in caplog.text


def test_every_permission_code_has_translations():
    from app.foundation.domain.permission_catalog import ALL_PERMISSION_CODES
    for locale in ('ar', 'en'):
        assert ALL_PERMISSION_CODES <= enum_catalog(locale)['foundation']['permissionName'].keys()
        assert ALL_PERMISSION_CODES <= enum_catalog(locale)['foundation']['permissionDescription'].keys()


def test_dashboards_do_not_label_enum_keys():
    app = Path(__file__).resolve().parents[2] / 'app'
    for file in app.glob('*/application/dashboard_service.py'):
        tree = ast.parse(file.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == 'labels' and isinstance(keyword.value, ast.DictComp):
                    # The only allowed identity label is actual user-entered work-center names.
                    assert isinstance(keyword.value.generators[0].iter, ast.Name)
                    assert keyword.value.generators[0].iter.id == 'by_center'
                if isinstance(node.func, ast.Name) and node.func.id == 'RankItem' and keyword.arg == 'label':
                    assert not (isinstance(keyword.value, ast.Name) and keyword.value.id in ('k', 'key', 'product_type', 'status'))
                if isinstance(node.func, ast.Name) and node.func.id == 'Attention' and keyword.arg == 'detail':
                    if isinstance(keyword.value, ast.Name) and keyword.value.id in ('category', 'status'):
                        assert any(k.arg == 'detail_kind' for k in node.keywords)
