"""Destructively reset only the configured IORP database, then migrate to head."""
import subprocess
import sys

from sqlalchemy import text

from app.core.db import engine


def main() -> int:
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    return subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"])


if __name__ == "__main__":
    raise SystemExit(main())
