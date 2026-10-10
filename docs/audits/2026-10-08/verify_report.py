"""Verify audit links and that inventoried backend sources have not changed."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
inventory = json.loads((HERE / 'inventory.json').read_text())
changed = [name for name, old in inventory['source_hashes'].items()
           if not (ROOT / name).exists() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != old]
report = (HERE / 'ASSESSMENT.md').read_text(encoding='utf-8')
broken = [link for link in re.findall(r'\]\(([^)]+)\)', report)
          if not link.startswith('http') and not (HERE / link).exists()]
result = {'backend_source_files': len(inventory['source_hashes']), 'changed_since_inventory': changed,
          'broken_report_artifact_links': broken}
(HERE / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
assert not changed and not broken
