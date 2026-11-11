"""Quotation document settings: the document language, the signature and the terms and conditions (QUOTE-DOC-001)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuoteTermInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title_ar: str | None = Field(default=None, max_length=120)
    title_en: str | None = Field(default=None, max_length=120)
    body_ar: str | None = Field(default=None, max_length=2000)
    body_en: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    @model_validator(mode='after')
    def written_in_a_language(self):
        """A term has a title and a text in at least one language; empty fields are kept as none."""
        for name in ('title_ar', 'title_en', 'body_ar', 'body_en'):
            setattr(self, name, getattr(self, name) or None)
        if not ((self.title_ar and self.body_ar) or (self.title_en and self.body_en)):
            raise ValueError('TERM_TEXT_REQUIRED')
        return self


class QuoteSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    # Every quotation is printed in this language, with the settings written in it.
    document_language: Literal['ar', 'en'] = 'ar'
    quote_validity_days: int = Field(default=10, ge=1, le=365, strict=True)
    signature_title_ar: str | None = Field(default=None, max_length=255)
    signature_title_en: str | None = Field(default=None, max_length=255)
    show_preparer_name: bool = False
    # The whole list, in display order: it replaces the current terms.
    terms: list[QuoteTermInput] = Field(default_factory=list, max_length=20)


class QuoteSettingsRead(QuoteSettingsUpdate):
    model_config = ConfigDict(extra='ignore')
