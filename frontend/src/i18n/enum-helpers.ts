import { useTranslations } from "next-intl";

export function getEnumLabel(
  entityName: string,
  fieldName: string,
  value: string | null | undefined,
  t: (key: string) => string,
): string {
  if (value == null) return "—";
  try {
    return t(`enums.${entityName}.${fieldName}.${value}`);
  } catch {
    return snakeCaseToTitleCase(value);
  }
}

export function useEnumLabel() {
  const t = useTranslations();
  return (entityName: string, fieldName: string, value: string | null | undefined) =>
    getEnumLabel(entityName, fieldName, value, t);
}

function snakeCaseToTitleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
