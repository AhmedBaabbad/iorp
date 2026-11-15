"""Customer names; the legacy display name remains Arabic-first for other modules."""
import unicodedata


def has_arabic_letter(value: str) -> bool:
    ranges = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x0870, 0x089F),
              (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
              (0x10EC0, 0x10EFF), (0x1EE00, 0x1EEFF))
    return any(unicodedata.category(char).startswith('L') and
               any(low <= ord(char) <= high for low, high in ranges) for char in value)


def normalized_names(payload: dict, current=None) -> dict:
    """Support legacy API writers without letting `name` override explicit names."""
    values = dict(payload)
    if not {'name_ar', 'name_en'} & values.keys() and values.get('name') is not None:
        legacy = values['name'].strip()
        language = 'name_ar' if has_arabic_letter(legacy) else 'name_en'
        values[language] = legacy
    for key in ('name_ar', 'name_en'):
        value = values.get(key, getattr(current, key, None))
        values[key] = value.strip() or None if value is not None else None
    if not values['name_ar'] and not values['name_en']:
        raise ValueError('CUSTOMER_NAME_REQUIRED')
    values['name'] = values['name_ar'] or values['name_en']
    return values


def document_customer_name(customer, language: str) -> str:
    preferred, other = ('name_ar', 'name_en') if language == 'ar' else ('name_en', 'name_ar')
    return getattr(customer, preferred, None) or getattr(customer, other, None) or customer.name
