import { readFileSync } from "node:fs";
import { attachEnumAliases } from "../src/i18n/shared-messages.ts";

export function resolveEnums(messages, locale) {
  const shared = JSON.parse(readFileSync(new URL(`../../shared/i18n/${locale}/enums.json`, import.meta.url), "utf8"));
  const aliases = JSON.parse(readFileSync(new URL("../../shared/i18n/aliases.json", import.meta.url), "utf8"));
  return attachEnumAliases(messages, shared, aliases);
}
