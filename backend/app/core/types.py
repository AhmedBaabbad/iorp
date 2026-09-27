from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BeforeValidator, EmailStr, Field, PlainSerializer
from app.core.security import normalize_email


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


ISODatetime = Annotated[
    datetime,
    PlainSerializer(_to_iso, return_type=str, when_used="json"),
]

ISOAwareDatetime = Annotated[
    AwareDatetime,
    PlainSerializer(_to_iso, return_type=str, when_used="json"),
]

def _require_ascii_email(value: str) -> str:
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("Email address must contain ASCII characters only") from exc
    return value


NormalizedEmail = Annotated[
    EmailStr,
    BeforeValidator(lambda value: normalize_email(value) if isinstance(value, str) else value),
    AfterValidator(_require_ascii_email),
    Field(max_length=255),
]
