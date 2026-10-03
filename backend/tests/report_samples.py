"""Where review samples (PDF, HTML, PNG) are written: never inside the project.

REPORT_SAMPLES_DIR when set, otherwise <system temp>/iorp-report-samples. The application stores no
reports; these files exist only for looking at the layout.
"""
import os
import tempfile
from pathlib import Path


def samples_dir(name: str) -> Path:
    root = Path(os.environ.get('REPORT_SAMPLES_DIR') or Path(tempfile.gettempdir()) / 'iorp-report-samples')
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    return path
