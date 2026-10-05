"""Phone numbers shared by every module: stored in international form ("+9665…"). Pure."""
import re

_DIGITS = {**{0x0660 + i: str(i) for i in range(10)}, **{0x06F0 + i: str(i) for i in range(10)}}


def normalize_phone(value: str | None) -> str | None:
    """A phone in international form; a Saudi local number ("05…", "011…") gets +966; Arabic digits are accepted.
    Empty gives None; anything else raises ValueError."""
    if value is None or not str(value).strip():
        return None
    text = re.sub(r"[\s\-().]", "", str(value).strip().translate(_DIGITS))
    if text.startswith("00"):
        text = "+" + text[2:]
    if re.fullmatch(r"0\d{8,9}", text):  # a Saudi local number: mobile 05…, landline 01…
        text = "+966" + text[1:]
    if not re.fullmatch(r"\+\d{8,15}", text):
        raise ValueError(str(value))
    return text
