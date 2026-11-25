"""Bilingual quality wording; the legacy key supports already-issued JSON snapshots."""
def wording(row, field, lang):
    get = row.get if isinstance(row, dict) else lambda key: getattr(row, key, None)
    for key in (f"{field}_{lang}", f"{field}_{'ar' if lang == 'en' else 'en'}", field):
        value = get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None
