export function displayValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  return String(value);
}

export function optionalText(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function toDatetimeLocalValue(date: Date): string {
  const offset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - offset * 60 * 1000);
  return local.toISOString().slice(0, 16);
}

/** Joins words with the list separator of the language: "أ، ب" in Arabic, "a, b" in English. */
export function joinList(values: (string | number | null | undefined)[], locale: string): string {
  return values.filter((v) => v !== null && v !== undefined && v !== "").join(locale === "ar" ? "، " : ", ");
}
