// Pure planning-lifecycle rules shared by the queue, demand detail and order detail.
// Quantities stay strings end to end; arithmetic uses integer thousandths (3 decimals).

export type PlanningView = "active" | "planned" | "all";
export const PLANNING_VIEWS: PlanningView[] = ["active", "planned", "all"];
export const PLANNABLE_STATUSES = ["ready_for_planning", "partially_planned"];
// Server rule: only orders without execution can give quantity back; the server also checks execution records.
export const RELEASABLE_ORDER_STATUSES = ["draft", "released"];

const STATUS_OPTIONS: Record<PlanningView, string[]> = {
  active: PLANNABLE_STATUSES,
  planned: [],
  all: ["draft", "ready_for_planning", "partially_planned", "planned", "cancelled"],
};

export function statusOptions(view: PlanningView) {
  return STATUS_OPTIONS[view];
}

export function parseView(value: string | null | undefined): PlanningView {
  return PLANNING_VIEWS.includes(value as PlanningView) ? (value as PlanningView) : "active";
}

export function planningQuery(view: PlanningView, filters: Record<string, string>, page: number, pageSize = 20) {
  const values = Object.entries(filters).filter(([key, value]) => value && (key !== "status" || statusOptions(view).includes(value)));
  return new URLSearchParams({ ...Object.fromEntries(values), view, page: String(page), page_size: String(pageSize) }).toString();
}

export function toMilli(value: string | null | undefined): bigint {
  const match = /^(-?)(\d+)(?:\.(\d{1,3}))?$/.exec(String(value ?? "0").trim());
  if (!match) return BigInt(0);
  const amount = BigInt(match[2]) * BigInt(1000) + BigInt((match[3] ?? "").padEnd(3, "0"));
  return match[1] ? -amount : amount;
}

export function fromMilli(value: bigint) {
  const sign = value < BigInt(0) ? "-" : "";
  const abs = value < BigInt(0) ? -value : value;
  const fraction = String(abs % BigInt(1000)).padStart(3, "0").replace(/0+$/, "");
  return `${sign}${abs / BigInt(1000)}${fraction ? `.${fraction}` : ""}`;
}

export type QuantityLike = { required_quantity: string; active_allocated_quantity?: string; allocated_quantity?: string; remaining_quantity?: string };

export function progress(item: QuantityLike) {
  const required = toMilli(item.required_quantity);
  const allocated = toMilli(item.active_allocated_quantity ?? item.allocated_quantity ?? "0");
  const remaining = item.remaining_quantity !== undefined ? toMilli(item.remaining_quantity) : required - allocated;
  const percent = required > BigInt(0) ? Number((allocated * BigInt(1000)) / required) / 10 : 0;
  return { required: fromMilli(required), allocated: fromMilli(allocated), remaining: fromMilli(remaining), percent, partial: allocated > BigInt(0) && remaining > BigInt(0) };
}

export function canReleaseFromOrder(orderStatus: string) {
  return RELEASABLE_ORDER_STATUSES.includes(orderStatus);
}

export function lifecycleErrorCode(error: unknown) {
  const details = (error as { details?: { detail?: { code?: string } }; status?: number } | null) ?? null;
  const code = details?.details?.detail?.code;
  if (code) return code;
  if (details?.status === 403) return "forbidden";
  return "request_failed";
}
