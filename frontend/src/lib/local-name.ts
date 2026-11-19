export type LocalizedName = { name_ar?: string | null; name_en?: string | null; name?: string | null };

/** User data: choose the UI language, then the other supplied name, then single-language text. */
export function localName(item: LocalizedName | null | undefined, locale: string): string {
  const ar = item?.name_ar?.trim(), en = item?.name_en?.trim();
  return (locale.startsWith("ar") ? ar || en : en || ar) || item?.name?.trim() || "";
}
