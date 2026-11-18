"""Document specification columns over product-catalog DTOs; no module imports."""
from dataclasses import dataclass
from app.core.specifications import format_spec_value
from app.core.units import unit_label


@dataclass(frozen=True)
class SpecificationColumns:
    headers: list[str]
    rows: list[list[str]]

    @property
    def landscape(self):
        return len(self.headers) > 6


def specification_columns(items, products, lang='ar', *, product_key=lambda i: i.product_type,
                          spec=lambda i: i.requested_spec_json) -> SpecificationColumns:
    items = list(items)
    definitions, order = {}, []
    for item in items:
        product = products.get(product_key(item))
        for prop in product.properties if product else ():
            if prop.key not in definitions:
                order.append(prop.key)
                definitions[prop.key] = []
            definitions[prop.key].append(prop)
    order = [key for key in order if any(
        (spec(i) or {}).get(key) not in (None, '') and
        any(p.key == key for p in products[product_key(i)].properties)
        for i in items if product_key(i) in products)]
    units = {key: {p.unit for p in definitions[key]} for key in order}
    headers = []
    for key in order:
        prop = definitions[key][0]
        title = prop.name_ar if lang == 'ar' else prop.name_en
        unit = next(iter(units[key])) if len(units[key]) == 1 else None
        headers.append(title + (f' ({unit_label(unit, lang)})' if unit else ''))
    rows, has_extra = [], False
    for item in items:
        values = spec(item) or {}
        product = products.get(product_key(item))
        props = {p.key: p for p in product.properties} if product else {}
        cells = []
        for key in order:
            value, prop = values.get(key), props.get(key)
            if value in (None, '') or prop is None:
                cells.append('—')
                continue
            if prop.kind == 'choice':
                value = next((o[1 if lang == 'ar' else 2] for o in prop.options if o[0] == str(value)), value)
            cells.append(format_spec_value(value, prop.unit if len(units[key]) > 1 else None, lang))
        extra = ' × '.join(f'{key}: {format_spec_value(value)}' if value not in (None, '') else key
                           for key, value in values.items() if key not in props)
        has_extra |= bool(extra)
        rows.append([*cells, extra or '—'])
    if has_extra:
        headers.append('مواصفات أخرى' if lang == 'ar' else 'Other specifications')
    else:
        rows = [row[:-1] for row in rows]
    return SpecificationColumns(headers, rows)
