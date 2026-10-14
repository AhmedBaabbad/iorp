"""Where production stores reference-list values (MD-003): a downtime's and a scrap record's reason (their names, as
written). Registered at the composition root so master data can count their use without touching these tables."""
from app.core.interfaces.reference_lists import holder_for
from app.production.infrastructure.models import DowntimeEvent, WasteRecord

HOLDERS = (
    holder_for("production", "downtime_reason", ((DowntimeEvent, DowntimeEvent.reason_code, lambda org: DowntimeEvent.organization_id == org),)),
    holder_for("production", "waste_reason", ((WasteRecord, WasteRecord.reason_code, lambda org: WasteRecord.organization_id == org),)),
)
