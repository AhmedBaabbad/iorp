export type CustomerName = { name?: string | null; name_ar?: string | null; name_en?: string | null; customer_name?: string | null; customer_name_ar?: string | null; customer_name_en?: string | null };

/** UI locale only. Quotation documents use the organization's document language. */
export function customerDisplayName(customer: CustomerName, locale: string): string {
  const ar = (customer.name_ar ?? customer.customer_name_ar)?.trim();
  const en = (customer.name_en ?? customer.customer_name_en)?.trim();
  return (locale.startsWith("ar") ? ar || en : en || ar) || customer.name || customer.customer_name || "";
}
