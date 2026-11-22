// Project a saved phone as the server will copy it; manual input never passes through this helper.
export function snapshotPhone(value: string | null | undefined): string {
  if (!value?.trim()) return "";
  let text = value.trim().replace(/[٠-٩۰-۹]/g, digit => String(digit.charCodeAt(0) - (digit >= "۰" ? 0x06f0 : 0x0660)))
    .replace(/[\s\-().]/g, "");
  if (text.startsWith("00")) text = "+" + text.slice(2);
  if (/^0\d{8,9}$/.test(text)) text = "+966" + text.slice(1);
  return /^\+\d{8,15}$/.test(text) ? text : "";
}
