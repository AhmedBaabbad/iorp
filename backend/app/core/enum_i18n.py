"""Shared enum labels for future printed documents; UI APIs continue returning keys."""
import json
import logging
import os
from functools import lru_cache
from pathlib import Path

_LOG = logging.getLogger(__name__)


def shared_root() -> Path:
    # Docker image /app/shared, or repository root/shared during development/tests.
    app_root = Path(__file__).resolve().parents[2]
    for root in (app_root / 'shared/i18n', app_root.parent / 'shared/i18n'):
        if (root / 'aliases.json').is_file():
            return root
    raise RuntimeError('Shared enum source missing')


@lru_cache(maxsize=2)
def enum_catalog(locale: str) -> dict:
    if locale not in ('ar', 'en'):
        raise ValueError('Unsupported enum locale')
    return json.loads((shared_root() / locale / 'enums.json').read_text(encoding='utf-8'))


def enum_label(module: str, field: str, value: str | None, locale: str) -> str:
    if value is None:
        return '—'
    label = enum_catalog(locale).get(module, {}).get(field, {}).get(value)
    if isinstance(label, str) and label:
        return label
    if os.environ.get('APP_ENV') != 'production':
        raise ValueError(f'Missing enum translation: {module}.{field}')
    _LOG.warning('Missing enum translation: %s.%s', module, field)
    return '—'
