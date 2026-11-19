# Delivery-note totals layout verification

Base: `71aafa7`. Synthetic example: 200 rolls × 9 kg and 150 rolls × 10 kg; gross 3500 kg.

The footer now shows total quantity (350 roll), total net weight (3300 kg), packaging and remainder (200 kg), and gross weight (3500 kg), in that order. Without gross weight, only the first two rows appear. Quantity spans the quantity/unit columns; weight values occupy the final column. All labels start at the same logical table edge. Only gross weight has a thick top separator and bold text.

Delivery columns use logical start alignment for number/description and centered alignment for other headers and values. Weight numbers alone are isolated with `bdi dir="ltr"`; the unit remains outside it in an LTR inline-flex group. Existing quantity formatting is unchanged.

Return notes had the same combined number/unit isolation problem. Their weight formatting uses the same correction, without changing return table alignment or totals layout. No business calculations, API, schema, migrations, or application images changed.

## Verification

- Shipping tests: **62 passed, 2 skipped**.
- Real-renderer PDF tests: **8 passed**, covering Arabic/English delivery notes with/without gross weight, return notes, and existing quotation PDFs.
- Extracted PDF assertions normalize Unicode presentation forms only and check number-before-unit ordering, total values, and footer order in both languages.
- Arabic and English delivery-note page images visually inspected after final rendering.

## Arabic

![Arabic delivery note](delivery-note-totals-layout/delivery-note-ar.png)

## English

![English delivery note](delivery-note-totals-layout/delivery-note-en.png)
