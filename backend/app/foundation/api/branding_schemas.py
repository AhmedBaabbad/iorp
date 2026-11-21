from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator


class BankAccountInput(BaseModel):
    """A company bank account printed on quotations. The IBAN is stored without spaces, upper case."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    bank_name_ar: str = Field(min_length=1, max_length=255)
    bank_name_en: str | None = Field(None, max_length=255)
    account_name: str | None = Field(None, max_length=255)
    account_number: str | None = Field(None, max_length=64)
    iban: str = Field(min_length=15, max_length=42)
    swift_code: str | None = Field(None, pattern=r'^[A-Za-z0-9]{8}([A-Za-z0-9]{3})?$')
    is_active: bool = True

    @field_validator('iban')
    @classmethod
    def normalized_iban(cls, value: str) -> str:
        iban = value.replace(' ', '').upper()
        if not (15 <= len(iban) <= 34 and iban[:2].isalpha() and iban[2:4].isdigit() and iban.isalnum()):
            raise ValueError('Invalid IBAN')
        return iban


class BrandingUpdate(BaseModel):
    """The company identity printed on every report and document (the single source; modules never hold these values)."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    legal_name_ar: str | None = Field(None, max_length=255)
    legal_name_en: str | None = Field(None, max_length=255)
    trade_name_ar: str | None = Field(None, max_length=255)
    trade_name_en: str | None = Field(None, max_length=255)
    # Saudi formats: CR 10 digits; VAT 15 digits starting and ending with 3; Unified No. 10 digits starting with 7.
    commercial_registration_no: str | None = Field(None, pattern=r'^\d{10}$')
    vat_number: str | None = Field(None, pattern=r'^3\d{13}3$')
    unified_number: str | None = Field(None, pattern=r'^7\d{9}$')
    descriptor_ar: str | None = Field(None, max_length=255)
    descriptor_en: str | None = Field(None, max_length=255)
    address_ar: str | None = Field(None, max_length=500)
    address_en: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=30)
    phone: str | None = Field(None, max_length=60)
    email: EmailStr | None = None
    website: str | None = Field(None, max_length=255)

    @field_validator('website')
    @classmethod
    def website_without_scheme(cls, value: str | None) -> str | None:
        # Printed as "factory.example.com": the scheme and a trailing slash add nothing on paper.
        if not value:
            return value
        for scheme in ('https://', 'http://'):
            if value.lower().startswith(scheme):
                value = value[len(scheme):]
        return value.rstrip('/') or None

    @field_validator('commercial_registration_no', 'vat_number', 'unified_number', mode='before')
    @classmethod
    def digits_only(cls, value):
        # Accept "314 8246 3520 0003" as typed; empty means not set.
        return value.replace(' ', '') or None if isinstance(value, str) else value
    report_footer_note_ar: str | None = Field(None, max_length=1000)
    report_footer_note_en: str | None = Field(None, max_length=1000)
    primary_color: str | None = Field(None, pattern=r'^#[0-9a-fA-F]{6}$')
    # None leaves the accounts unchanged; a list replaces them in this order.
    bank_accounts: list[BankAccountInput] | None = Field(None, max_length=10)
