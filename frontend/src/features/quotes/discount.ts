/**
 * The quotation arithmetic as the server applies it (backend commercial/domain/pricing.py), for the live preview:
 * each line's discount is a percentage of the line, rounded to the halala; VAT is taken on what remains.
 */
export const money = (value: number) => Math.round((value + Number.EPSILON) * 100) / 100;

export function lineAmounts(quantity: string | number, unitPrice: string | number, percent: string | number) {
  const total = money(Number(quantity || 0) * Number(unitPrice || 0));
  const discount = money(total * Number(percent || 0) / 100);
  return { total, discount, net: money(total - discount) };
}

export function quoteAmounts(lines: { quantity: string; unit_price: string; discount_percent: string }[], vatRate: number, includeTax: boolean) {
  const amounts = lines.map((l) => lineAmounts(l.quantity, l.unit_price, l.discount_percent));
  const subtotal = money(amounts.reduce((sum, a) => sum + a.total, 0));
  const discount = money(amounts.reduce((sum, a) => sum + a.discount, 0));
  const afterDiscount = money(subtotal - discount);
  const tax = includeTax ? money(Math.max(0, afterDiscount) * vatRate / 100) : 0;
  return { amounts, subtotal, discount, afterDiscount, tax, total: money(afterDiscount + tax) };
}

/** A percentage typed by the user: 0-100, at most two decimals; anything else is not a valid discount. */
export const validPercent = (value: string) => value === "" || (/^\d{1,3}(\.\d{1,2})?$/.test(value) && Number(value) <= 100);
