import { P } from "@/lib/production-permissions";
import { Q } from "@/lib/quality-permissions";
import { S } from "@/lib/shipping-permissions";
import { PR } from "@/lib/procurement-permissions";

export const DEPARTMENTS = [
  { key: "commercial", href: "/commercial-dashboard", tone: "var(--accent)", permissions: ["commercial:customers:read", "commercial:quotes:read", "commercial:orders:read", "commercial:samples:read", "commercial:follow_ups:read"] },
  { key: "production", href: "/production", tone: "var(--warning)", permissions: [P.ORDERS_READ, P.RESULTS_READ, P.DOWNTIME_READ, P.DEMANDS_READ] },
  { key: "quality", href: "/quality-dashboard", tone: "var(--teal)", permissions: [Q.CHECKS_READ, Q.REJECTIONS_READ, Q.DEFECTS_READ, Q.NCR_READ, Q.COA_READ] },
  { key: "shipping", href: "/shipping-dashboard", tone: "var(--purple)", permissions: [S.SHIPMENTS_READ, S.RETURNS_READ] },
  { key: "procurement", href: "/procurement-dashboard", tone: "var(--success)", permissions: [PR.SUPPLIERS_READ, PR.PO_READ, PR.RECEIPTS_READ] },
] as const;
export type Department = typeof DEPARTMENTS[number]["key"];
