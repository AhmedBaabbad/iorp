"""PROJECT-FILES-003: one file policy. Uploads are checked by their content, photos and logos are made small, PDFs are kept
as sent, only the storage key and metadata are in the database, the organization's quota holds, nothing is left half
written, and a closed record's files are archived, never deleted."""
import hashlib
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID

import pytest
from PIL import Image

from app.core import files
from app.core.config import settings
from app.core.storage import LocalFileStorage
from app.core.tenancy import TenantContext
from app.foundation.infrastructure.models import Organization
from app.quality.infrastructure.models import NCRAttachment
from tests.file_samples import pdf, photo, png
from tests.quality.test_ncr import ncr  # noqa: F401  (fixture with the quality permissions)


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    return LocalFileStorage(str(tmp_path))


class MemoryStorage:
    """Another storage behind the same interface (as S3 or MinIO would be): nothing else changes."""

    def __init__(self):
        self.files = {}

    def put(self, key, content):
        self.files[key] = content

    def read(self, key):
        return self.files[key]

    def delete(self, key):
        self.files.pop(key, None)

    def exists(self, key):
        return key in self.files

    def resolve(self, key):
        raise FileNotFoundError(key)


def ncr_service(db, org, user, storage):
    from app.quality.application.ncr_service import NCRService
    tenant = TenantContext(user_id=user.id, organization_id=org.id, is_organization_root=True)
    service = NCRService(db, tenant, storage=storage)
    report = service.open_report(source_type="other", report_type="other", title="Torn film", description="Evidence")
    db.commit()
    return service, report


# ── the policy ───────────────────────────────────────────────────────────────────────────────────

def test_a_file_over_the_limit_is_refused():
    with pytest.raises(files.FileRejected) as caught:
        files.prepare(b"%PDF-1.7\n" + b"x" * settings.file_pdf_max_upload + b"\n%%EOF", "attachment")
    assert caught.value.code == "TOO_LARGE" and caught.value.limit == settings.file_pdf_max_upload
    with pytest.raises(files.FileRejected) as caught:
        files.prepare(png() + b"\0" * settings.file_logo_max_upload, "logo")
    assert caught.value.code == "TOO_LARGE"


def test_the_screens_read_the_limits_from_the_one_policy(client, auth_headers):
    body = client.get("/api/v1/organization/storage", headers=auth_headers).json()
    assert body["policy"]["attachment"]["max_bytes"]["application/pdf"] == settings.file_pdf_max_upload
    assert body["policy"]["attachment"]["max_bytes"]["image/jpeg"] == settings.file_image_max_upload
    assert body["policy"]["logo"]["types"] == ["image/png", "image/jpeg", "image/webp"]
    assert body["quota_bytes"] == settings.file_organization_quota and body["used_bytes"] == 0


@pytest.mark.parametrize("content", [b"MZ\x90\x00 an executable", b"<svg onload=alert(1)>", b"PK\x03\x04 a docx", b"plain text"])
def test_a_type_that_is_not_allowed_is_refused_whatever_its_name(content):
    with pytest.raises(files.FileRejected) as caught:
        files.prepare(content, "attachment")
    assert caught.value.code == "UNSUPPORTED_TYPE"
    with pytest.raises(files.FileRejected):
        files.prepare(pdf(), "logo")  # a logo is an image


def test_a_phone_photo_is_stored_small_readable_and_without_camera_data():
    original = photo()
    assert len(original) > 1_000_000
    prepared = files.prepare(original, "attachment")
    image = Image.open(BytesIO(prepared.content))
    assert prepared.media_type == "image/webp" and prepared.size <= settings.file_image_max_stored
    assert max(image.size) == settings.file_image_max_px and image.size == (1280, 960)  # proportions kept
    assert not image.getexif() and "exif" not in image.info


def test_a_logo_is_stored_within_50_kb():
    prepared = files.prepare(photo((1600, 1600), exif=False), "logo")
    assert prepared.size <= settings.file_logo_max_stored and max(Image.open(BytesIO(prepared.content)).size) <= settings.file_logo_max_px


def test_a_pdf_is_kept_exactly_as_sent():
    original = pdf(b"page " * 1000)
    prepared = files.prepare(original, "attachment")
    assert prepared.content == original and prepared.checksum == hashlib.sha256(original).hexdigest()
    with pytest.raises(files.FileRejected) as caught:
        files.prepare(b"%PDF-1.7\ncut short", "attachment")
    assert caught.value.code == "INVALID_PDF"


# ── storage, metadata, isolation ─────────────────────────────────────────────────────────────────

def test_the_users_file_name_is_never_the_stored_name_and_only_metadata_is_in_the_database(db, test_org, test_user, storage):
    service, report = ncr_service(db, test_org, test_user, storage)
    service.add_attachment(report.id, "../../etc/passwd.png", png())
    row = db.query(NCRAttachment).one()
    key = row.storage_path
    assert key.startswith(f"organizations/{test_org.id}/quality/") and "passwd" not in key and ".." not in key
    assert key.endswith(".webp") and storage.exists(key)
    assert row.file_name == "../../etc/passwd.png" and row.size_bytes == len(storage.read(key))  # the name is only shown
    assert row.checksum == hashlib.sha256(storage.read(key)).hexdigest()
    assert {c.name for c in NCRAttachment.__table__.columns}.isdisjoint({"content", "data", "blob"})


def test_another_organization_cannot_download_the_file(ncr, db, storage):
    from tests.quality.test_ncr import ROOT
    from app.dependencies import get_current_user
    from app.main import app
    report = ncr.create()
    [item] = ncr.client.post(f"{ROOT}/{report['id']}/attachments", files=dict(file=("a.png", png()))).json()
    assert ncr.client.get(f"{ROOT}/{report['id']}/attachments/{item['id']}").status_code == 200  # authorised: yes
    other = Organization(name="Other Files", code="OTHER-FILES", timezone="UTC")
    db.add(other); db.commit()
    mine = app.dependency_overrides[get_current_user]()
    outsider = SimpleNamespace(**{**vars(mine), "tenant": TenantContext(user_id=mine.user.id, organization_id=other.id, is_organization_root=True)})
    app.dependency_overrides[get_current_user] = lambda: outsider
    from app.dependencies import get_current_tenant
    app.dependency_overrides[get_current_tenant] = lambda: outsider.tenant
    assert ncr.client.get(f"{ROOT}/{report['id']}/attachments/{item['id']}").status_code == 404


def test_a_failed_storage_leaves_no_row_and_a_failed_row_leaves_no_file(db, test_org, test_user, storage, monkeypatch):
    service, report = ncr_service(db, test_org, test_user, storage)
    monkeypatch.setattr(storage, "put", lambda key, content: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        service.add_attachment(report.id, "a.png", png())
    assert db.query(NCRAttachment).count() == 0
    monkeypatch.undo()
    monkeypatch.setattr(settings, "uploads_dir", str(storage.root))
    original_commit = db.commit
    monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(RuntimeError("database down")))
    with pytest.raises(RuntimeError):
        service.add_attachment(report.id, "a.png", png())
    monkeypatch.setattr(db, "commit", original_commit)
    assert db.query(NCRAttachment).count() == 0 and not [p for p in storage.root.rglob("*") if p.is_file()]


def test_the_organization_quota_is_kept(db, test_org, test_user, storage):
    service, report = ncr_service(db, test_org, test_user, storage)
    service.add_attachment(report.id, "a.pdf", pdf(b"x" * 2000))
    test_org.storage_quota_bytes = files.usage(db, test_org.id) + 100  # room for 100 more bytes only
    db.commit()
    from app.quality.domain.rules import QualityError
    with pytest.raises(QualityError) as caught:
        service.add_attachment(report.id, "b.pdf", pdf(b"y" * 2000))
    assert caught.value.code == "FILE_QUOTA_EXCEEDED"
    assert db.query(NCRAttachment).count() == 1


def test_files_stored_before_the_policy_still_open(ncr, db, test_org, storage):
    """A key of the old form (no year, the original bytes) is read as it is."""
    from tests.quality.test_ncr import ROOT
    from app.quality.infrastructure.models import NonConformanceReport
    report = ncr.create()
    legacy = f"organizations/{test_org.id}/quality/old-file.pdf"
    storage.put(legacy, pdf())
    found = db.get(NonConformanceReport, UUID(report["id"]))
    db.add(NCRAttachment(organization_id=test_org.id, ncr_id=found.id, file_name="old.pdf", content_type="application/pdf",
                         size_bytes=len(pdf()), storage_path=legacy, uploaded_by_user_id=found.detected_by_user_id or found.owner_user_id or ncr.user.id))
    db.commit()
    [item] = ncr.client.get(f"{ROOT}/{report['id']}").json()["attachments"]
    assert ncr.client.get(f"{ROOT}/{report['id']}/attachments/{item['id']}").content == pdf()


def test_the_storage_can_be_replaced_without_touching_a_model(db, test_org, test_user):
    memory = MemoryStorage()
    service, report = ncr_service(db, test_org, test_user, memory)
    service.add_attachment(report.id, "a.png", png())
    row = db.query(NCRAttachment).one()
    assert row.storage_path in memory.files and memory.files[row.storage_path].startswith(b"RIFF")


def test_a_closed_records_file_is_archived_not_deleted(db, test_org, test_user, storage):
    from app.quality.domain import ncr as N
    service, report = ncr_service(db, test_org, test_user, storage)
    service.add_attachment(report.id, "a.png", png())
    row = db.query(NCRAttachment).one()
    report.status = sorted(N.FINAL)[0]
    db.commit()
    [kept] = service.remove_attachment(report.id, row.id)
    assert kept["archived_at"] is not None and storage.exists(row.storage_path)


def test_an_open_records_file_is_deleted_and_its_space_freed(db, test_org, test_user, storage):
    service, report = ncr_service(db, test_org, test_user, storage)
    service.add_attachment(report.id, "a.png", png())
    row = db.query(NCRAttachment).one()
    used = files.usage(db, test_org.id)
    assert used > 0 and service.remove_attachment(report.id, row.id) == []
    assert files.usage(db, test_org.id) == 0 and not storage.exists(row.storage_path)
