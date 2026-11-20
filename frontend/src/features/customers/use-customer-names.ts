"use client";
import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { customersByIds } from "./customer-api";
import { customerDisplayName, type CustomerName } from "@/lib/customer-name";

/** One batched lookup per visible set; copied single-language names remain the fallback. */
export function useCustomerNames(ids: (string | null | undefined)[]) {
  const locale = useLocale();
  const key = [...new Set(ids.filter((id): id is string => Boolean(id)))].sort().join(",");
  const [state, setState] = useState<{ key: string; names: Record<string, CustomerName> }>({ key: "", names: {} });
  useEffect(() => {
    let active = true;
    if (key) customersByIds(key.split(",")).then(rows => {
      if (active) setState({ key, names: Object.fromEntries(rows.map(row => [row.id, row])) });
    }).catch(() => undefined);
    return () => { active = false; };
  }, [key]);
  return (id: string | null | undefined, stored?: string | null) =>
    (id && state.key === key && state.names[id] ? customerDisplayName(state.names[id], locale) : stored) || "—";
}
