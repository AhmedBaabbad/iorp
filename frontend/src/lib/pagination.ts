"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

/** One page of a server list (backend core/pagination.py): the rows, the total that matches, and the page count. */
export type Page<T> = { items: T[]; total: number; page: number; page_size: number; pages: number };

export const PAGE_SIZES = [25, 50, 100] as const;
export const DEFAULT_PAGE_SIZE = 50;

/**
 * A list's page, page size, search and filters, kept in the address (?page=2&search=gulf): a refresh, the back button or
 * a shared link opens the same page. Changing a filter or the search goes back to page 1.
 */
export function useListQuery<K extends string>(filterKeys: readonly K[]) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const size = Number(params.get("page_size"));
  const pageSize = (PAGE_SIZES as readonly number[]).includes(size) ? size : DEFAULT_PAGE_SIZE;
  const keys = filterKeys.join("|");
  const filters = useMemo(
    () => Object.fromEntries(filterKeys.map((k) => [k, params.get(k) ?? ""])) as Record<K, string>,
    [params, keys], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const update = useCallback((patch: Record<string, string | number | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(patch)) {
      if (value === null || value === "" || (key === "page" && Number(value) === 1) || (key === "page_size" && Number(value) === DEFAULT_PAGE_SIZE)) next.delete(key);
      else next.set(key, String(value));
    }
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }, [params, pathname, router]);

  return {
    page, pageSize, filters,
    setPage: (value: number) => update({ page: value }),
    setPageSize: (value: number) => update({ page_size: value, page: 1 }),
    setFilter: (key: K, value: string) => update({ [key]: value, page: 1 }),
    /** Several filters at once (e.g. a filter and an older alias of it); back to page 1. */
    setFilters: (patch: Partial<Record<K, string>>) => update({ ...patch, page: 1 }),
    clearFilters: () => update({ ...Object.fromEntries(filterKeys.map((k) => [k, null])), page: 1 }),
    /** The query string for the API: page, page_size and the filters that are set. */
    apiQuery: () => new URLSearchParams([["page", String(page)], ["page_size", String(pageSize)],
      ...filterKeys.filter((k) => filters[k]).map((k) => [k, filters[k]] as [string, string])]).toString(),
  };
}

type FilterValue = string | boolean;
const ALL = "all";

/**
 * useListQuery for a list whose filters have defaults (CAPA opens on "open") or yes/no switches, and older link names
 * (`aliases`: ?order= for production_order_id). The filters and page stay in the address; a change goes back to page 1.
 * A filter chosen as "all" while its default is something else is kept as "all" in the address so a refresh keeps it.
 */
export function usePagedFilters<T extends Record<string, FilterValue>>(defaults: T, aliases: Record<string, keyof T & string> = {}) {
  const names = Object.keys(defaults) as (keyof T & string)[];
  const list = useListQuery([...names, ...Object.keys(aliases)]);
  const aliasOf = (name: string) => Object.entries(aliases).find(([, target]) => target === name)?.[0];
  const filters = Object.fromEntries(names.map((name) => {
    const raw = list.filters[name] || (aliasOf(name) ? list.filters[aliasOf(name)!] : "");
    const fallback = defaults[name];
    if (!raw) return [name, fallback];
    if (raw === ALL) return [name, typeof fallback === "boolean" ? false : ""];
    return [name, typeof fallback === "boolean" ? raw === "true" : raw];
  })) as T;
  const encode = (name: keyof T, value: FilterValue) => {
    if (value === defaults[name]) return null;
    if (value === "" || value === false) return defaults[name] ? ALL : null;
    return String(value);
  };
  const alias = (name: string) => (aliasOf(name) ? { [aliasOf(name)!]: "" } : {});
  return {
    filters, page: list.page, pageSize: list.pageSize, setPage: list.setPage, setPageSize: list.setPageSize,
    set: (name: keyof T & string, value: FilterValue) => list.setFilters({ [name]: encode(name, value) ?? "", ...alias(name) }),
    clear: () => list.clearFilters(),
    /** The filters that are set, as query values, with the page: for the API. */
    query: () => Object.fromEntries([...Object.entries(filters).filter(([, v]) => v !== "" && v !== false).map(([k, v]) => [k, String(v)]),
      ["page", String(list.page)], ["page_size", String(list.pageSize)]]) as Record<string, string>,
  };
}

/** The page numbers to show: the first, the last, and two around the current one, with gaps ("…") between. */
export function pageNumbers(page: number, pages: number): (number | "gap")[] {
  const wanted = new Set([1, pages, page - 2, page - 1, page, page + 1, page + 2].filter((n) => n >= 1 && n <= pages));
  const sorted = [...wanted].sort((a, b) => a - b);
  return sorted.flatMap((n, i) => (i > 0 && n - sorted[i - 1] > 1 ? ["gap" as const, n] : [n]));
}
