import { readFile } from "fs/promises";
import path from "path";

import type { Locale } from "./config";

const LOCALES_DIR = path.join(process.cwd(), "src", "i18n", "locales");

function expandDottedKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(expandDottedKeys);
  if (value === null || typeof value !== "object") return value;

  const output: Record<string, unknown> = {};
  for (const [rawKey, rawValue] of Object.entries(value as Record<string, unknown>)) {
    const parts = rawKey.split(".");
    let target = output;
    for (const part of parts.slice(0, -1)) {
      const existing = target[part];
      if (existing === null || typeof existing !== "object" || Array.isArray(existing)) {
        target[part] = {};
      }
      target = target[part] as Record<string, unknown>;
    }
    target[parts.at(-1)!] = expandDottedKeys(rawValue);
  }
  return output;
}

async function readLocaleFile(locale: Locale, filename: string): Promise<Record<string, unknown>> {
  const content = await readFile(path.join(LOCALES_DIR, locale, filename), "utf-8");
  return expandDottedKeys(JSON.parse(content)) as Record<string, unknown>;
}

export async function loadMessages(locale: Locale) {
  const [
    auth,
    common,
    navigation,
    enums,
    messages,
    commercial,
    production,
    quality,
    ncr,
    capa,
    dashboard,
    workforce,
    administration,
    setup,
    platform,
    organization,
    orgStatus,
    profile,
    platformAudit,
    tenantAudit,
    platformSecurity,
    platformActivity,
    tenantSecurity,
    tenantActivity,
    effectiveAccess,
    passwordReset,
  ] = await Promise.all([
    readLocaleFile(locale, "auth.json"),
    readLocaleFile(locale, "common.json"),
    readLocaleFile(locale, "navigation.json"),
    readLocaleFile(locale, "enums.json"),
    readLocaleFile(locale, "messages.json"),
    readLocaleFile(locale, "commercial.json"),
    readLocaleFile(locale, "production.json"),
    readLocaleFile(locale, "quality.json"),
    readLocaleFile(locale, "ncr.json"),
    readLocaleFile(locale, "capa.json"),
    readLocaleFile(locale, "dashboard.json"),
    readLocaleFile(locale, "workforce.json"),
    readLocaleFile(locale, "administration.json"),
    readLocaleFile(locale, "setup.json"),
    readLocaleFile(locale, "platform.json"),
    readLocaleFile(locale, "organization.json"),
    readLocaleFile(locale, "org-status.json"),
    readLocaleFile(locale, "profile.json"),
    readLocaleFile(locale, "platform-audit.json"),
    readLocaleFile(locale, "tenant-audit.json"),
    readLocaleFile(locale, "platform-security.json"),
    readLocaleFile(locale, "platform-activity.json"),
    readLocaleFile(locale, "tenant-security.json"),
    readLocaleFile(locale, "tenant-activity.json"),
    readLocaleFile(locale, "effective-access.json"),
    readLocaleFile(locale, "password-reset.json"),
  ]);

  const reports = await readLocaleFile(locale, "reports.json");
  const shipping = await readLocaleFile(locale, "shipping.json");
  const procurement = await readLocaleFile(locale, "procurement.json");
  const masterdata = await readLocaleFile(locale, "masterdata.json");
  const notifications = await readLocaleFile(locale, "notifications.json");
  const logs = await readLocaleFile(locale, "logs.json");
  return {
    notifications,
    logs,
    reports,
    shipping,
    procurement,
    masterdata,
    auth,
    common,
    navigation,
    enums,
    messages,
    commercial,
    production,
    quality,
    ncr,
    capa,
    dashboard,
    workforce,
    administration,
    setup,
    platform,
    organization,
    orgStatus,
    profile,
    platformAudit,
    tenantAudit,
    platformSecurity,
    platformActivity,
    tenantSecurity,
    tenantActivity,
    effectiveAccess,
    passwordReset,
  };
}
