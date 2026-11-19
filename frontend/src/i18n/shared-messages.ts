import { readFile } from "fs/promises";
import path from "path";

/** A single source on disk. Docker supplies ./shared; local development reads ../shared. */
export async function sharedMessages(locale: string) {
  const roots = [path.join(process.cwd(), "shared", "i18n"), path.join(process.cwd(), "..", "shared", "i18n")];
  let root = roots[0];
  try { await readFile(path.join(root, "aliases.json")); } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    root = roots[1];
  }
  const shared = JSON.parse(await readFile(path.join(root, locale, "enums.json"), "utf8"));
  const aliases: Record<string, string> = JSON.parse(await readFile(path.join(root, "aliases.json"), "utf8"));
  return { shared, aliases };
}

/** Legacy namespace paths reference the shared dictionaries, without a second translation source. */
export function attachEnumAliases(messages: Record<string, unknown>, shared: Record<string, Record<string, unknown>>, aliases: Record<string, string>) {
  for (const [oldPath, target] of Object.entries(aliases)) {
    const parts = oldPath.split(".");
    let node = messages;
    for (const part of parts.slice(0, -1)) node = (node[part] ??= {}) as Record<string, unknown>;
    node[parts.at(-1)!] = target.split(".").reduce<unknown>((value, part) => (value as Record<string, unknown>)[part], shared);
  }
  messages.sharedEnums = shared;
  return messages;
}
