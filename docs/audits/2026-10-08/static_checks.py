"""Read-only metadata/secret-pattern audit; never prints matching secret values."""
import importlib.metadata as md
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
folder = Path(__file__).parent
tracked = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
patterns = {'private_key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
            'aws_key': r'\bAKIA[0-9A-Z]{16}\b', 'github_token': r'\bgh[pousr]_[A-Za-z0-9]{30,}\b',
            'slack_token': r'\bxox[baprs]-[A-Za-z0-9-]{20,}\b'}
matches = []
for name in tracked:
    path = ROOT / name
    if not path.is_file() or path.stat().st_size > 2_000_000: continue
    try: source = path.read_text(encoding='utf-8')
    except UnicodeError: continue
    for kind, pattern in patterns.items():
        for match in re.finditer(pattern, source):
            matches.append({'file': name, 'line': source.count('\n', 0, match.start()) + 1, 'kind': kind})
versions = {}
for package in ['fastapi', 'starlette', 'python-jose', 'python-multipart', 'Pillow', 'pypdf', 'SQLAlchemy', 'bcrypt', 'pydantic', 'uvicorn']:
    try: versions[package] = md.version(package)
    except md.PackageNotFoundError: versions[package] = 'NOT INSTALLED'
inventory = json.loads((folder / 'inventory.json').read_text())
result = {'tracked_real_env_files': [p for p in tracked if Path(p).name == '.env'],
          'secret_signature_candidates': matches, 'limitations': 'Current tracked files only; no history or general credential/high-entropy scanner. A zero count is not proof of no secrets.',
          'python_installed_versions': versions,
          'tables_without_direct_organization': [{'name': t['name'], 'foreign_keys': t['foreign_keys']} for t in inventory['tables'] if not t['tenant_column']]}
(folder / 'static-checks.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k != 'tables_without_direct_organization'}, indent=2))
