"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState, type CSSProperties } from "react";

import { sharedStyles } from "@/styles/shared-styles";
import type { CustomerOption } from "@/types/customers";
import { customersByIds, lookupCustomers } from "./customer-api";

/**
 * Choosing a customer without loading them all: type part of the code or name and the server answers the first 20
 * matches. The chosen customer stays in the list while searching, so the form never loses it.
 */
export function CustomerPicker({ value, onChange, disabled, required = true, style, ariaLabel }: {
  value: string; onChange: (id: string, customer?: CustomerOption) => void; disabled?: boolean; required?: boolean;
  style?: CSSProperties; ariaLabel?: string;
}) {
  const t = useTranslations("commercial.customers.picker");
  const [search, setSearch] = useState("");
  const [options, setOptions] = useState<CustomerOption[]>([]);
  const [chosen, setChosen] = useState<CustomerOption | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const timer = setTimeout(() => {
      lookupCustomers(search).then((rows) => { if (active) setOptions(rows); })
        .catch(() => { if (active) setOptions([]); }).finally(() => { if (active) setLoading(false); });
    }, search ? 250 : 0);
    return () => { active = false; clearTimeout(timer); };
  }, [search]);

  useEffect(() => {
    // A value set by the form (an edit, a quotation's customer) is shown by name even if it is not among the matches.
    if (!value) { setChosen(null); return; }
    if (chosen?.id === value) return;
    const found = options.find((o) => o.id === value);
    if (found) { setChosen(found); return; }
    let active = true;
    customersByIds([value]).then((rows) => { if (active) setChosen(rows[0] ?? null); }).catch(() => undefined);
    return () => { active = false; };
  }, [value, options]); // eslint-disable-line react-hooks/exhaustive-deps

  const shown = chosen && !options.some((o) => o.id === chosen.id) ? [chosen, ...options] : options;
  return (
    <span style={{ display: "grid", gap: 6 }}>
      <input type="search" style={{ ...sharedStyles.input, ...style }} value={search} disabled={disabled} placeholder={t("search")}
        aria-label={t("search")} onChange={(e) => setSearch(e.target.value)} />
      <select style={{ ...sharedStyles.input, ...style }} value={value} required={required} disabled={disabled} aria-label={ariaLabel}
        onChange={(e) => onChange(e.target.value, shown.find((o) => o.id === e.target.value))}>
        <option value="">{loading ? t("loading") : shown.length ? t("choose") : t("none")}</option>
        {shown.map((o) => <option key={o.id} value={o.id}>{o.name} ({o.customer_code})</option>)}
      </select>
    </span>
  );
}
