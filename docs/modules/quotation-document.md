# QUOTE-DOC-001 — Quotation document (PDF)

The quotation PDF is downloaded from the quotation page in Arabic or English: «تنزيل العرض PDF».

## What it prints

1. **Letterhead.** The shared external header (reporting.md, "Corporate document identity"): logo, names, tagline and bar.
2. **Title and details.** "عرض سعر / Quotation", then a strip with the date, the quotation number and its validity date.
3. **Customer.** To, Attention and Subject, all taken from the quote.
4. **Products and prices.** Each line shows its number and description, the quantity and unit, and the unit price and amount in the quote's currency.
   - **Description:** the line's description in the document language. If that is empty, the other language is used, then the product and its specification.
   - **Unit:** printed by its name from the units list.
   - **Totals:** subtotal, discount (if any), VAT with its rate, and the total including VAT.
5. **Notes.** The quote's notes, if any.
6. **Terms and conditions.** The organization's active terms, in their order and in the document language. Where a term has no English text, the Arabic text is printed.
7. **Signature.** «مع خالص التحية،», the company name, the signature title (default «مدير المبيعات» / "Sales Manager") and, optionally, the name of the person who prepared the quote.
8. **Footer (every page).** The shared external footer:
   - Legal line: CR, Unified No. and VAT.
   - Contacts: address, phone, e-mail and website.
   - One line per active bank account: bank, account name, account number, IBAN and SWIFT.
   - The quotation number and "page X of Y".

## Settings

- **Quotation settings** (`/quotes/settings`, `commercial:quote_settings:read|update`): the signature title (Arabic and English), the "show the preparer's name" option, and the terms. Each term has a title and a text in both languages, an active flag and a position. "Add the usual headings" inserts Technical specification, Validity, Prices, Delivery and Payment.
  - Terms are company settings, not part of a quote: every quotation prints the current active terms, so a change applies to the next download.
- **Bank accounts:** company identity (`/admin/organization`), several allowed. The IBAN is stored without spaces, in upper case, and validated. Only active accounts are printed.

## Quote changes

| Change | Detail |
|---|---|
| `attention`, `subject` | New quote fields |
| `tax_rate` | The VAT %. When it is sent, the server computes `tax_amount = (subtotal − discount) × rate`, rounded to 0.01, on create and on every update. The browser no longer decides the amount. "Include VAT" (15%) is ticked by default on new quotes. |
| `description_ar`, `description_en` | Per item, optional and folded away ("Custom printed description"). Left empty, the product and its specification are printed |
| Specification | Entered as "property / value" rows. They are stored as the same `requested_spec_json`, which commercial orders and production read unchanged; numbers and true/false keep their type |
| Units | A grouped dropdown of 35 factory units with Arabic and English names. The list lives in `commercial/domain/units.py` and is mirrored in `frontend/src/features/quotes/quote-units.ts`; a test keeps both identical. Units saved as free text before the list still show and print as written. |
| Numbering | New quotations are numbered `QT-YYYY-NNNN`. The yearly sequence continues after earlier `RFQ-` numbers, and existing numbers are unchanged. Editing stays open in every status, as before. |

## Architecture

- **Registration.** The document is registered with the reporting core as `customers.quotation`. It has its own page template; its header and footer are the core's external identity (`classification="external"`). It is not listed in the report centers (`listed=False`). These hooks are generic; the core has nothing quotation-specific.
- **Access.** Generating it needs `commercial:quotes:read` and `commercial:customers:read`, within the caller's customer scope: a sales representative only gets their own customers' quotations.
- **Endpoints.** `GET /api/v1/commercial/quotes/{id}/document.pdf?lang=ar|en`, or `POST /api/v1/reports/customers.quotation/pdf|preview` with `{quote_id, lang}`.
- **Migration.** `f6a1b2i3` creates the settings, terms and bank account tables, adds the quote and item columns, and adds the two settings permissions, granted to the organization administrator and commercial manager system roles. It can be reversed.
- **Tests.** `tests/commercial/test_quotation_document.py` covers VAT, settings, IBAN validation, the Arabic and English content, fallbacks, access, and real PDF samples written outside the project (`<temp>/iorp-report-samples/quotation/`).
