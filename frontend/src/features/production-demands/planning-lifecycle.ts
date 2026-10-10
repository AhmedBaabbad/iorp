// Pure planning-lifecycle rules shared by the queue, demand detail and order detail.
// Quantities stay strings end to end; arithmetic uses integer thousandths (3 decimals).

export const PLANNABLE_STATUSES = ["ready_for_planning", "partially_planned"];
// Mirror of the server's ALLOCATION_OPEN (domain/order_lifecycle.py): allocations are added, changed and released while
// the order is open; completed, closed and cancelled orders keep them as they are. The server decides; this only hides
// a button that would be refused.
export const ALLOCATION_OPEN_STATUSES = ["draft", "released", "in_progress", "on_hold"];
// Which statuses the queue shows, and its query: status-visibility.ts (PLANNING).

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
  return ALLOCATION_OPEN_STATUSES.includes(orderStatus);
}

export function lifecycleErrorCode(error: unknown) {
  const details = (error as { details?: { detail?: { code?: string } }; status?: number } | null) ?? null;
  const code = details?.details?.detail?.code;
  if (code) return code;
  if (details?.status === 403) return "forbidden";
  return "request_failed";
}
