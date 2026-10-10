"""Files kept with a shipment or a return (SHIP-004): the signed delivery note as proof of delivery, photos of damage.

Images (PNG, JPEG, WebP) and PDFs only, recognised by their content; 10 MB at most. Stored under the organization's
folder by the core storage; nothing generated is ever stored here.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.storage import InvalidAttachmentError, LocalFileStorage, save_attachment, compensate_new_file
from app.shipping.domain import returns as R
from app.shipping.domain import rules
from app.shipping.domain.rules import ShippingError
from app.shipping.infrastructure.models import Shipment, ShipmentReturn, ShippingAttachment
from .support import attachments

SHIPMENT_KINDS = ("proof_of_delivery", "document")
RETURN_KINDS = ("photo", "document")
LEFT = frozenset({rules.DISPATCHED, rules.RETURNED, *rules.RECEIVED, rules.NOT_DELIVERED})  # proof exists once goods left
MAX_FILES = 20


class AttachmentService:
    def __init__(self, db, tenant, storage: LocalFileStorage | None = None):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id
        self.storage = storage or LocalFileStorage()

    def _shipment(self, shipment_id) -> Shipment:
        shipment = self.db.scalar(select(Shipment).where(Shipment.id == shipment_id, Shipment.organization_id == self.org))
        if shipment is None:
            raise ShippingError("SHIPMENT_NOT_FOUND", 404)
        return shipment

    def _return(self, return_id) -> ShipmentReturn:
        found = self.db.scalar(select(ShipmentReturn).where(ShipmentReturn.id == return_id, ShipmentReturn.organization_id == self.org))
        if found is None:
            raise ShippingError("RETURN_NOT_FOUND", 404)
        return found

    def _save(self, shipment_id, return_id, kind, file_name, content) -> list[dict]:
        count = len(attachments(self.db, self.org, shipment_id=shipment_id, return_id=return_id))
        if count >= MAX_FILES:
            raise ShippingError("TOO_MANY_FILES", 400, limit=MAX_FILES)
        try:
            path, content_type = save_attachment(content, self.org, "shipping", self.storage)
        except InvalidAttachmentError as exc:
            raise ShippingError(f"FILE_{exc}", 400) from exc
        with compensate_new_file(self.db, self.storage, path, lambda: self.db.scalar(select(ShippingAttachment.id).where(
                ShippingAttachment.organization_id == self.org, ShippingAttachment.storage_path == path)) is not None):
            self.db.add(ShippingAttachment(organization_id=self.org, shipment_id=shipment_id, return_id=return_id, kind=kind,
                                       file_name=(file_name or "file")[-255:], content_type=content_type, size_bytes=len(content),
                                       storage_path=path, uploaded_by_user_id=self.tenant.user_id))
            self.db.commit()
        return attachments(self.db, self.org, shipment_id=shipment_id, return_id=return_id)

    def add_to_shipment(self, shipment_id, kind, file_name, content) -> list[dict]:
        if kind not in SHIPMENT_KINDS:
            raise ShippingError("ATTACHMENT_KIND_UNKNOWN", 400)
        shipment = self._shipment(shipment_id)
        if shipment.status not in LEFT:
            raise ShippingError("SHIPMENT_NOT_DISPATCHED", shipment_status=shipment.status)
        return self._save(shipment.id, None, kind, file_name, content)

    def add_to_return(self, return_id, kind, file_name, content) -> list[dict]:
        if kind not in RETURN_KINDS:
            raise ShippingError("ATTACHMENT_KIND_UNKNOWN", 400)
        found = self._return(return_id)
        if found.status in R.VOID:
            raise ShippingError("RETURN_IS_FINAL", return_status=found.status)
        return self._save(found.shipment_id, found.id, kind, file_name, content)

    def _row(self, attachment_id, shipment_id=None, return_id=None) -> ShippingAttachment:
        query = select(ShippingAttachment).where(ShippingAttachment.id == attachment_id, ShippingAttachment.organization_id == self.org)
        query = query.where(ShippingAttachment.return_id == return_id) if return_id else query.where(
            ShippingAttachment.shipment_id == shipment_id, ShippingAttachment.return_id.is_(None))
        row = self.db.scalar(query)
        if row is None:
            raise ShippingError("ATTACHMENT_NOT_FOUND", 404)
        return row

    def file(self, attachment_id, shipment_id=None, return_id=None):
        """(path on disk, content type, file name) to send back."""
        row = self._row(attachment_id, shipment_id, return_id)
        try:
            path = self.storage.resolve(row.storage_path)
        except FileNotFoundError as exc:
            raise ShippingError("ATTACHMENT_NOT_FOUND", 404) from exc
        if not path.is_file():
            raise ShippingError("ATTACHMENT_NOT_FOUND", 404)
        return path, row.content_type, row.file_name

    def remove(self, attachment_id, shipment_id=None, return_id=None) -> list[dict]:
        row = self._row(attachment_id, shipment_id, return_id)
        path = row.storage_path
        self.db.delete(row)
        self.db.commit()
        try:
            self.storage.delete(path)
        except FileNotFoundError:
            pass
        return attachments(self.db, self.org, shipment_id=shipment_id, return_id=return_id)
