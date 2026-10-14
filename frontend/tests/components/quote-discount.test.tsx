// SALES-DISC-001: the quotation preview applies each line's discount before VAT, exactly as the server does.
import { expect, it } from 'vitest';
import { lineAmounts, quoteAmounts, validPercent } from '@/features/quotes/discount';

const lines = [{ quantity: '2000', unit_price: '95', discount_percent: '10' }, { quantity: '150', unit_price: '60', discount_percent: '' }];

it('takes the discount off one line only, then VAT on what remains', () => {
  const r = quoteAmounts(lines, 15, true);
  expect(r.amounts.map((a) => a.net)).toEqual([171000, 9000]);
  expect([r.subtotal, r.discount, r.afterDiscount, r.tax, r.total]).toEqual([199000, 19000, 180000, 27000, 207000]);
});

it('puts the same percentage on every line', () => {
  const r = quoteAmounts(lines.map((l) => ({ ...l, discount_percent: '10' })), 15, true);
  expect([r.discount, r.afterDiscount, r.tax, r.total]).toEqual([19900, 179100, 26865, 205965]);
});

it('rounds each line to the halala like the server and accepts only 0-100 %', () => {
  expect(lineAmounts('7', '12.35', '7')).toEqual({ total: 86.45, discount: 6.05, net: 80.4 });
  expect(quoteAmounts(lines, 15, false).tax).toBe(0);
  expect(['', '10', '7.5', '100'].every(validPercent)).toBe(true);
  expect(['101', '-1', '1.234', 'x'].some(validPercent)).toBe(false);
});
