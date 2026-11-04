"""Backup image entrypoint. No application startup or unrelated app secrets."""
import os
from pathlib import Path

from iorp_backup import backup


if __name__ == '__main__':
    backup(Path('/backup-out'), None, True, url_override=os.environ['DATABASE_URL'],
           uploads_dir=Path('/var/lib/iorp/uploads'))
