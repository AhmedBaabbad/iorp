"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { lookupProductionOrders } from "../api/production-orders-api";
import type { ProductionOrderListItem } from "../types";

/**
 * Choosing a production order without loading them all (ARCH-PAGE-001): type part of the number or product and the server
 * answers the first 20 matches, optionally among some statuses. The chosen order stays listed while searching.
 */
export function ProductionOrderPicker({ value, onChange, statuses = [], disabled, required, emptyLabel, ariaLabel, className }: {
  value: string; onChange: (id: string, order?: ProductionOrderListItem) => void; statuses?: string[]; disabled?: boolean; required?: boolean;
  emptyLabel?: string; ariaLabel?: string; className?: string;
}) {
  const t = useTranslations("production.productionOrders.picker");
  const [search, setSearch] = useState("");
  const [options, setOptions] = useState<ProductionOrderListItem[]>([]);
  const [chosen, setChosen] = useState<ProductionOrderListItem | null>(null);
  const [loading, setLoading] = useState(false);
  const wanted = statuses.join(",");

  useEffect(() => {
    let active = true;
    setLoading(true);
    const timer = setTimeout(() => {
      lookupProductionOrders({ search, statuses: wanted ? wanted.split(",") : [] }).then(rows => { if (active) setOptions(rows); })
        .catch(() => { if (active) setOptions([]); }).finally(() => { if (active) setLoading(false); });
    }, search ? 250 : 0);
    return () => { active = false; clearTimeout(timer); };
  }, [search, wanted]);

  useEffect(() => {
    // An order set from outside (the address, an edit) is shown by its number even when it is not among the matches.
    if (!value) { setChosen(null); return; }
    if (chosen?.id === value) return;
    const found = options.find(o => o.id === value);
    if (found) { setChosen(found); return; }
    let active = true;
    lookupProductionOrders({ ids: [value] }).then(rows => { if (active) setChosen(rows[0] ?? null); }).catch(() => undefined);
    return () => { active = false; };
  }, [value, options]); // eslint-disable-line react-hooks/exhaustive-deps

  const shown = chosen && !options.some(o => o.id === chosen.id) ? [chosen, ...options] : options;
  return <span style={{ display: "grid", gap: 6 }}>
    <input type="search" className={className} value={search} disabled={disabled} placeholder={t("search")} aria-label={t("search")}
      onChange={e => setSearch(e.target.value)} />
    <select className={className} value={value} required={required} disabled={disabled} aria-label={ariaLabel}
      onChange={e => onChange(e.target.value, shown.find(o => o.id === e.target.value))}>
      <option value="">{loading ? t("loading") : emptyLabel ?? (shown.length ? t("choose") : t("none"))}</option>
      {shown.map(o => <option key={o.id} value={o.id}>{o.production_order_number} — {o.product_type}</option>)}
    </select>
  </span>;
}
