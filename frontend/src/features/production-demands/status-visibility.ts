// Which demand statuses a list shows (demands list and planning queue). The server filters
// (statuses=...), so paging and totals stay right; the choice lives in the URL (shareable,
// survives reload) and in this browser, separately per screen.
import type { DemandStatus } from "./api";

export const ALL_STATUSES: DemandStatus[] = ["draft", "ready_for_planning", "partially_planned", "planned", "cancelled"];
const URL_PARAM = "statuses";

export type Visibility = { defaults: DemandStatus[]; storageKey: string };
// Finished demands crowd the list as planning grows; they stay one click away.
export const DEMANDS: Visibility = { defaults: ["draft", "ready_for_planning", "partially_planned"], storageKey: "iorp.production.demands.visibleStatuses" };
// The planning queue opens on what can still be planned.
export const PLANNING: Visibility = { defaults: ["ready_for_planning", "partially_planned"], storageKey: "iorp.production.planning.visibleStatuses" };
export const DEFAULT_VISIBLE = DEMANDS.defaults;

/** Known statuses in canonical order; null when nothing usable was given. */
export function parseStatuses(value: string | null | undefined): DemandStatus[] | null {
  if (!value) return null;
  const chosen = new Set(value.split(","));
  const statuses = ALL_STATUSES.filter(s => chosen.has(s));
  return statuses.length ? statuses : null;
}

export function serialize(statuses: DemandStatus[]) {
  return ALL_STATUSES.filter(s => statuses.includes(s)).join(",");
}

/** URL first (a shared link), then this browser's last choice, then the screen's default. */
export function initialStatuses(urlValue: string | null, stored: string | null, defaults: DemandStatus[] = DEFAULT_VISIBLE): DemandStatus[] {
  return parseStatuses(urlValue) ?? parseStatuses(stored) ?? defaults;
}

/** Toggle one status; the last visible status cannot be hidden (an empty list would show nothing). */
export function toggle(statuses: DemandStatus[], status: DemandStatus): DemandStatus[] {
  if (statuses.includes(status)) return statuses.length > 1 ? statuses.filter(s => s !== status) : statuses;
  return ALL_STATUSES.filter(s => s === status || statuses.includes(s));
}

export const isAll = (statuses: DemandStatus[]) => ALL_STATUSES.every(s => statuses.includes(s));
export const sameStatuses = (a: DemandStatus[], b: DemandStatus[]) => serialize(a) === serialize(b);
export const isDefault = (statuses: DemandStatus[], defaults: DemandStatus[] = DEFAULT_VISIBLE) => sameStatuses(statuses, defaults);

/** Query pairs for the API: none when every status is shown. */
export function statusQuery(statuses: DemandStatus[]): [string, string][] {
  return isAll(statuses) ? [] : ALL_STATUSES.filter(s => statuses.includes(s)).map(s => [URL_PARAM, s]);
}

/** The page URL carries the choice only when it differs from the screen's default. */
export function withStatusesInUrl(search: string, statuses: DemandStatus[], defaults: DemandStatus[] = DEFAULT_VISIBLE) {
  const params = new URLSearchParams(search);
  params.delete("view"); // links from before the status picker
  if (isDefault(statuses, defaults)) params.delete(URL_PARAM); else params.set(URL_PARAM, serialize(statuses));
  return params;
}

export function readStored(key: string = DEMANDS.storageKey): string | null {
  try { return window.localStorage.getItem(key); } catch { return null; }
}

export function store(statuses: DemandStatus[], key: string = DEMANDS.storageKey) {
  try { window.localStorage.setItem(key, serialize(statuses)); } catch { /* private mode: the URL still keeps it */ }
}

// ---- planning queue ----------------------------------------------------------------------------

/** The planning queue proper (sequence order, reordering, allocation) is shown when exactly the plannable statuses are chosen. */
export function isActiveQueue(statuses: DemandStatus[]) {
  return sameStatuses(statuses, PLANNING.defaults);
}

/** Planning statuses from the URL: the statuses param, or a link from the former tabs (view=planned / view=all). */
export function planningStatusesFromUrl(statuses: string | null, view: string | null): DemandStatus[] | null {
  return parseStatuses(statuses) ?? (view === "planned" ? ["planned"] : view === "all" ? [...ALL_STATUSES] : null);
}

export function planningQuery(statuses: DemandStatus[], filters: Record<string, string>, page: number, pageSize = 20) {
  const values = Object.entries(filters).filter(([key, value]) => value && key !== "status");
  const active = isActiveQueue(statuses);
  // The active queue sends its statuses too, so the server reports how many demands it hides.
  const chosen: [string, string][] = active ? PLANNING.defaults.map(s => [URL_PARAM, s]) : statusQuery(statuses);
  return new URLSearchParams([...values, ["view", active ? "active" : "all"], ...chosen, ["page", String(page)], ["page_size", String(pageSize)]]).toString();
}
