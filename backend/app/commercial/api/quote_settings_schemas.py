"""Quotation document settings: signature and bilingual terms and conditions (QUOTE-DOC-001)."""
from pydantic import BaseModel, ConfigDict, Field


class QuoteTermInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title_ar: str = Field(min_length=1, max_length=120)
    title_en: str | None = Field(default=None, max_length=120)
    body_ar: str = Field(min_length=1, max_length=2000)
    body_en: str | None = Field(default=None, max_length=2000)
    is_active: bool = True


class QuoteSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    signature_title_ar: str | None = Field(default=None, max_length=255)
    signature_title_en: str | None = Field(default=None, max_length=255)
    show_preparer_name: bool = False
    # The whole list, in display order: it replaces the current terms.
    terms: list[QuoteTermInput] = Field(default_factory=list, max_length=20)


class QuoteSettingsRead(QuoteSettingsUpdate):
    model_config = ConfigDict(extra='ignore')
