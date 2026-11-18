"""Numeric specification values shared by all modules. No persistence or HTTP."""
from decimal import Decimal, InvalidOperation


class SpecificationValueError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise SpecificationValueError('SPEC_RANGE_NUMBER')
    number = Decimal(str(value))
    if not number.is_finite():
        raise SpecificationValueError('SPEC_RANGE_NUMBER')
    return number


def normalize_numeric(value, allows_range=False):
    if not isinstance(value, dict):
        finite_number(value)
        return value
    if not allows_range:
        raise SpecificationValueError('SPEC_RANGE_NOT_ALLOWED')
    if set(value) != {'min', 'max'}:
        raise SpecificationValueError('SPEC_RANGE_SHAPE')
    low, high = finite_number(value['min']), finite_number(value['max'])
    if low > high:
        raise SpecificationValueError('SPEC_RANGE_REVERSED')
    return value['min'] if low == high else dict(min=value['min'], max=value['max'])


def numeric_bounds(value):
    """Sorting/quality also read legacy numeric strings; invalid values return None."""
    try:
        if isinstance(value, dict):
            normalize_numeric(value, True)
            return finite_number(value['min']), finite_number(value['max'])
        if isinstance(value, bool) or value is None:
            return None
        number = Decimal(str(value).strip())
        return (number, number) if number.is_finite() else None
    except (ValueError, InvalidOperation, TypeError):
        return None


def format_spec_value(value, unit=None, lang='en'):
    """Scalar values keep their old spelling; range endpoints share decimal precision."""
    if isinstance(value, dict) and set(value) == {'min', 'max'} and (bounds := numeric_bounds(value)):
        low, high = bounds
        places = max(0, -low.as_tuple().exponent, -high.as_tuple().exponent)
        text = f'{low:.{places}f} – {high:.{places}f}' if low != high else str(value['min'])
    elif isinstance(value, dict):
        text = '; '.join(f'{key}: {format_spec_value(item, lang=lang)}' for key, item in value.items())
    elif isinstance(value, list):
        text = ', '.join(format_spec_value(item, lang=lang) for item in value)
    else:
        text = '' if value is None else str(value)
    if text and unit:
        from app.core.units import unit_label
        text += ' ' + unit_label(unit, lang)
    return text


def thickness_value(minimum, maximum=None):
    def number(value):
        decimal = finite_number(Decimal(str(value)))
        return int(decimal) if decimal == decimal.to_integral_value() else float(decimal)
    if minimum is None:
        return None
    if maximum is None or minimum == maximum:
        return number(minimum)
    return {'min': number(minimum), 'max': number(maximum)}
