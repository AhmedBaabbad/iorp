# Specification values

`frontend/src/lib/spec-value.ts` owns value formatting. Ranges use an en dash and the larger decimal precision of their endpoints: `{min: 0.7, max: 0.75}` displays as `0.70 – 0.75`. Persisted numeric JSON does not preserve the original spelling of a scalar; while editing, the exact text is retained separately.

`specificationRows` and `formatSpecification` own full-specification presentation: template order, localized property and choice names, formatted value and unit. Unknown historical properties remain visible. Callers provide their translated fallback labels and unit labels. `specText` delegates to the same formatter for value-only summaries. JSX must not coerce specification values with `String` or render JSON directly; the source regression test enforces this.

Numeric inputs keep strings while typing, including incomplete input and trailing zeros. Validity is enforced before submission and the visible validation message appears on blur. SpecEditor converts its draft on blur; save boundaries independently call `normalizeSpecDraft`, so submitting with Enter also converts opted-in numeric template values. Demand and sample forms normalize only at submission. Historical extra objects/ranges that were not edited remain intact.

The server already formats numeric intervals through `app.core.specifications.format_spec_value`. Quotation rendering, shared specification columns used by production documents/certificates, demand exports, quality summaries, and shipping thickness fields use it. Regression tests cover `0.70 – 0.75` through these paths. No schema or migration is required.
