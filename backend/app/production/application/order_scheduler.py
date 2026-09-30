"""In-process scheduler for date-based production order starts (PRODUCTION_AUTO_START_BY_DATE).

Runs auto_start_due_orders every PRODUCTION_AUTO_START_INTERVAL_MINUTES. The job is idempotent
and skips rows another transaction holds, so running it in several server processes is safe.
"""
import asyncio
import logging
from app.core.config import settings
from app.core.db import SessionLocal
from app.production.application.order_status_service import auto_start_due_orders

log = logging.getLogger(__name__)


def run_once() -> int:
    with SessionLocal() as db:
        return auto_start_due_orders(db)  # each organization's local date


async def auto_start_loop(stop: asyncio.Event) -> None:
    interval = settings.production_auto_start_interval_minutes * 60
    while not stop.is_set():
        try:
            started = await asyncio.to_thread(run_once)
            if started:
                log.info("Auto-started %s production order(s) whose planned start date arrived", started)
        except Exception:  # keep the loop alive; the next run retries
            log.exception("Production order auto-start run failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
