import base64
from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from app.core.storage import LocalFileStorage, InvalidLogoError
from app.foundation.api.branding_schemas import BrandingUpdate
from app.foundation.infrastructure.branding_models import BankAccount, OrganizationBranding, StoredAsset
from app.foundation.infrastructure.models import Organization
from app.foundation.infrastructure.models import User
from app.foundation.application.audit import log_tenant_audit, ORG_LOGO_UPLOADED, ORG_LOGO_REMOVED, ORG_PROFILE_UPDATED
from app.core.reporting.assets import PLACEHOLDER_LOGO


class BrandingService:
    """The only writer of company identity and logos.

    The logo's source of truth is the branding row's stored asset. organization.logo_path is
    a mirror kept in step here (same transaction) for existing consumers of the profile logo;
    nothing else writes it, and reads prefer the asset.
    """

    def __init__(self, db, storage=None):
        self.db, self.storage = db, storage or LocalFileStorage()

    def _organization(self, org_id, lock=False):
        query = select(Organization).where(Organization.id == org_id)
        return self.db.scalar(query.with_for_update() if lock else query)

    def get_branding(self, org_id):
        org = self._organization(org_id)
        if org is None:
            raise LookupError('Organization not found')
        row = self.db.get(OrganizationBranding, org_id)
        fields = {name: getattr(row, name, None) for name in BrandingUpdate.model_fields if name != 'bank_accounts'}
        fields['bank_accounts'] = [dict(bank_name_ar=a.bank_name_ar, bank_name_en=a.bank_name_en, account_name=a.account_name,
                                        account_number=a.account_number, iban=a.iban, swift_code=a.swift_code, is_active=a.is_active)
                                   for a in self.db.scalars(select(BankAccount).where(BankAccount.organization_id == org_id)
                                                            .order_by(BankAccount.sort_order, BankAccount.id))]
        fields.update(name=org.name, timezone=org.timezone, default_locale=org.default_locale,
                      logo_asset_id=getattr(row, 'logo_asset_id', None), secondary_logo_asset_id=getattr(row, 'secondary_logo_asset_id', None))
        fields['logo_data_uri'] = self._logo(org_id, fields['logo_asset_id'], org.logo_path)
        fields['secondary_logo_data_uri'] = self._logo(org_id, fields['secondary_logo_asset_id'], placeholder=False)
        return fields

    def _logo(self, org_id, asset_id, legacy_path=None, placeholder=True):
        asset = self.db.scalar(select(StoredAsset).where(StoredAsset.id == asset_id, StoredAsset.organization_id == org_id)) if asset_id else None
        key = asset.storage_key if asset else legacy_path
        if key and self.storage.exists(key):
            content = self.storage.resolve(key).read_bytes()
            _, media = self.storage.validate_logo_content(content)
        elif placeholder:
            content = PLACEHOLDER_LOGO.read_bytes()
            media = 'image/png'
        else:
            return None
        return 'data:' + media + ';base64,' + base64.b64encode(content).decode()

    def _row(self, org_id):
        org = self._organization(org_id, lock=True)
        if org is None:
            raise LookupError('Organization not found')
        row = self.db.get(OrganizationBranding, org_id)
        if row is None:
            row = OrganizationBranding(organization_id=org_id)
            self.db.add(row)
        return org, row

    def update(self, org_id, data, actor_id):
        org, row = self._row(org_id)
        values = data.model_dump()
        accounts = values.pop('bank_accounts')
        for name, value in values.items():
            setattr(row, name, value)
        if accounts is not None:
            for old in self.db.scalars(select(BankAccount).where(BankAccount.organization_id == org_id)):
                self.db.delete(old)
            self.db.flush()
            self.db.add_all(BankAccount(organization_id=org_id, sort_order=index, **account) for index, account in enumerate(accounts))
        row.updated_by_user_id = actor_id
        self._audit(org, actor_id, ORG_PROFILE_UPDATED)
        self.db.commit()
        return self.get_branding(org_id)

    def upload(self, org_id, content, actor_id, secondary=False):
        self.storage.validate_logo_content(content)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as im:
                    if im.width * im.height > 16_000_000:
                        raise InvalidLogoError('Image dimensions too large')
                    im.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise InvalidLogoError('Invalid image') from exc
        org, row = self._row(org_id)
        old_id = row.secondary_logo_asset_id if secondary else row.logo_asset_id
        old_path = org.logo_path if not secondary else None
        key = self.storage.save_logo_content(content, org_id)
        try:
            _, media = self.storage.validate_logo_content(content)
            asset = StoredAsset(organization_id=org_id, storage_key=key, media_type=media)
            self.db.add(asset); self.db.flush()
            setattr(row, 'secondary_logo_asset_id' if secondary else 'logo_asset_id', asset.id)
            row.updated_by_user_id = actor_id
            if not secondary:
                org.logo_path = key  # compatibility: existing authenticated logo consumers
            self._audit(org, actor_id, ORG_LOGO_UPLOADED)
            self.db.commit()
        except Exception:
            self.db.rollback(); self.storage.delete(key); raise
        self._discard(org_id, old_id, old_path)
        return self.get_branding(org_id)

    def remove(self, org_id, actor_id, secondary=False):
        org, row = self._row(org_id)
        old_id = row.secondary_logo_asset_id if secondary else row.logo_asset_id
        old_path = org.logo_path if not secondary else None
        setattr(row, 'secondary_logo_asset_id' if secondary else 'logo_asset_id', None)
        row.updated_by_user_id = actor_id
        if not secondary:
            org.logo_path = None
        self._audit(org, actor_id, ORG_LOGO_REMOVED)
        self.db.commit()
        self._discard(org_id, old_id, old_path)
        return self.get_branding(org_id)

    def _audit(self, org, actor_id, action):
        actor = self.db.scalar(select(User).where(User.organization_id == org.id, User.id == actor_id)) if actor_id else None
        log_tenant_audit(self.db, org.id, action, 'organization', org.id, actor_id,
                         actor.full_name if actor else None, actor.email if actor else None, org.name)

    def _discard(self, org_id, asset_id, legacy_path):
        asset = self.db.scalar(select(StoredAsset).where(StoredAsset.organization_id == org_id, StoredAsset.id == asset_id)) if asset_id else None
        if asset and self.db.scalar(select(OrganizationBranding.organization_id).where(
                OrganizationBranding.organization_id == org_id,
                (OrganizationBranding.logo_asset_id == asset.id) | (OrganizationBranding.secondary_logo_asset_id == asset.id))):
            return
        key = asset.storage_key if asset else legacy_path
        if asset:
            self.db.delete(asset); self.db.commit()
        if key:
            self.storage.delete(key)
