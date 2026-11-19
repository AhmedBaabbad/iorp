/** Never show a raw translation key or synthesize an English label. */
export function missingTranslation(namespace: string): string {
  if (process.env.NODE_ENV !== "production") throw new Error(`Missing enum translation: ${namespace}`);
  console.warn(`Missing enum translation: ${namespace}`);
  return "—";
}
