import { useTranslations } from "next-intl";
import { missingTranslation as missingEnum } from "./missing-message";
export { missingEnum };

export function getEnumLabel(
  entityName: string,
  fieldName: string,
  value: string | null | undefined,
  t: (key: string) => string,
): string {
  if (value == null) return "—";
  try {
    const key = `enums.${entityName}.${fieldName}.${value}`;
    const label = t(key);
    return label === key || label.endsWith(`.${key}`) ? missingEnum(`${entityName}.${fieldName}`) : label;
  } catch {
    return missingEnum(`${entityName}.${fieldName}`);
  }
}

export function useEnumLabel(): (entity: string, field: string, value: string | null | undefined) => string;
export function useEnumLabel(module: string): (field: string, value: string | null | undefined) => string;
export function useEnumLabel(module: string, field: string): (value: string | null | undefined) => string;
export function useEnumLabel(module?: string, field?: string) {
  const t = useTranslations();
  if (module && !field) return (category: string, value: string | null | undefined) => {
    if (value == null) return "—";
    const key = `sharedEnums.${module}.${category}.${value}`;
    return t.has(key) ? t(key) : missingEnum(`${module}.${category}`);
  };
  if (module && field) return (value: string | null | undefined) => {
    if (value == null) return "—";
    const key = `sharedEnums.${module}.${field}.${value}`;
    return t.has(key) ? t(key) : missingEnum(`${module}.${field}`);
  };
  return (entityName: string, fieldName: string, value: string | null | undefined) =>
    getEnumLabel(entityName, fieldName, value, t);
}
