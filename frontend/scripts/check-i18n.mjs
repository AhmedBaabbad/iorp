import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const localesRoot = path.join(process.cwd(), "src", "i18n", "locales");
const mojibakeMarkers = ["Ã", "Â", "Ø", "Ù", "â€", "ï¿½", "�"];

function leafKeys(value, prefix = "") {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return [prefix];
  return Object.entries(value).flatMap(([key, child]) =>
    leafKeys(child, prefix ? `${prefix}.${key}` : key),
  );
}

const englishFiles = (await readdir(path.join(localesRoot, "en"))).filter((name) => name.endsWith(".json")).sort();
const arabicFiles = (await readdir(path.join(localesRoot, "ar"))).filter((name) => name.endsWith(".json")).sort();
if (JSON.stringify(englishFiles) !== JSON.stringify(arabicFiles)) {
  throw new Error("Arabic and English locale file sets do not match.");
}

for (const filename of englishFiles) {
  const enText = await readFile(path.join(localesRoot, "en", filename), "utf8");
  const arText = await readFile(path.join(localesRoot, "ar", filename), "utf8");
  const badMarkers = mojibakeMarkers.filter((marker) => arText.includes(marker));
  if (badMarkers.length > 0) throw new Error(`${filename}: Arabic mojibake markers found: ${badMarkers.join(", ")}`);
  const enKeys = leafKeys(JSON.parse(enText)).sort();
  const arKeys = leafKeys(JSON.parse(arText)).sort();
  if (JSON.stringify(enKeys) !== JSON.stringify(arKeys)) {
    const missingArabic = enKeys.filter((key) => !arKeys.includes(key));
    const missingEnglish = arKeys.filter((key) => !enKeys.includes(key));
    throw new Error(`${filename}: locale key mismatch; missing ar=[${missingArabic.join(", ")}], missing en=[${missingEnglish.join(", ")}]`);
  }
}

console.log(`i18n check passed: ${englishFiles.length} Arabic/English JSON file pairs are valid and aligned.`);
