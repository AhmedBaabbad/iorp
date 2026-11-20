import { localName } from "./local-name";
export type CustomerName = { name?: string | null; name_ar?: string | null; name_en?: string | null; customer_name?: string | null; customer_name_ar?: string | null; customer_name_en?: string | null };

/** UI locale only. Quotation documents use the organization's document language. */
export function customerDisplayName(customer: CustomerName, locale: string): string {
  return localName({ name_ar: customer.name_ar ?? customer.customer_name_ar, name_en: customer.name_en ?? customer.customer_name_en, name: customer.name || customer.customer_name }, locale);
}
