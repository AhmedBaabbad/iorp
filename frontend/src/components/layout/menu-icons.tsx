// DASH-002: an icon for every page of the sidebar, drawn in the same line style as the section icons (24×24, 1.8 stroke).
import type { ReactNode } from "react";

type IconProps = { size?: number };

function icon(paths: ReactNode) {
  return function MenuIcon({ size = 16 }: IconProps) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round"
        strokeLinejoin="round" aria-hidden="true">{paths}</svg>
    );
  };
}

// ── general ─────────────────────────────────────────────────────────────────────────────────────────────────────
export const IconDashboard = icon(<><path d="M3 13h8V3H3z" /><path d="M13 21h8V11h-8z" /><path d="M3 21h8v-6H3z" /><path d="M13 3v6h8V3z" /></>);
export const IconReport = icon(<><path d="M4 20V10" /><path d="M10 20V4" /><path d="M16 20v-7" /><path d="M22 20H2" /></>);
export const IconSettings = icon(<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></>);
export const IconList = icon(<><path d="M8 6h13" /><path d="M8 12h13" /><path d="M8 18h13" /><path d="M3 6h.01" /><path d="M3 12h.01" /><path d="M3 18h.01" /></>);

// ── customers and sales ────────────────────────────────────────────────────────────────────────────────────────
export const IconCustomers = icon(<><circle cx="9" cy="7" r="4" /><path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" /><path d="M16 3.1a4 4 0 0 1 0 7.8" /><path d="M21 21v-2a4 4 0 0 0-3-3.9" /></>);
export const IconChat = icon(<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />);
// A customer complaint: a message carrying a concern.
export const IconComplaint = icon(<><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /><path d="M12 7v4" /><path d="M12 14h.01" /></>);
export const IconBell = icon(<><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></>);
export const IconFlask = icon(<><path d="M9 3h6" /><path d="M10 3v6L4.5 18.5A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.5L14 9V3" /><path d="M7 15h10" /></>);
export const IconQuote = icon(<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M8 13h8" /><path d="M8 17h5" /></>);
export const IconCart = icon(<><circle cx="9" cy="21" r="1" /><circle cx="20" cy="21" r="1" /><path d="M1 1h4l2.7 13.4a2 2 0 0 0 2 1.6h9.7a2 2 0 0 0 2-1.6L23 6H6" /></>);
export const IconBadge = icon(<><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="9" cy="10" r="2" /><path d="M15 8h2" /><path d="M15 12h2" /><path d="M7 16h10" /></>);

// ── production ─────────────────────────────────────────────────────────────────────────────────────────────────
export const IconMachine = icon(<><rect x="2" y="7" width="20" height="14" rx="2" /><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" /><circle cx="12" cy="14" r="3" /></>);
export const IconClock = icon(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>);
export const IconCrew = icon(<><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4" /><path d="M8 2v4" /><path d="M3 10h18" /><circle cx="12" cy="15" r="2" /></>);
export const IconInbox = icon(<><path d="M22 12h-6l-2 3h-4l-2-3H2" /><path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1z" /></>);
export const IconPlanning = icon(<><path d="M8 6h13" /><path d="M8 12h13" /><path d="M8 18h13" /><path d="M3 5l1 1 2-2" /><path d="M3 11l1 1 2-2" /><path d="M3 17l1 1 2-2" /></>);
export const IconWorkOrder = icon(<><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M9 3V1h6v2" /><path d="M9 9h6" /><path d="M9 13h6" /><path d="M9 17h3" /></>);
export const IconBoxCheck = icon(<><path d="M21 8 12 3 3 8v8l9 5 9-5z" /><path d="M3 8l9 5 9-5" /><path d="M12 13v8" /></>);
export const IconPause = icon(<><circle cx="12" cy="12" r="9" /><path d="M10 9v6" /><path d="M14 9v6" /></>);
export const IconTrash = icon(<><path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /></>);

// ── quality ────────────────────────────────────────────────────────────────────────────────────────────────────
export const IconInspect = icon(<><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /><path d="m8.5 11 2 2 3.5-3.5" /></>);
export const IconReject = icon(<><circle cx="12" cy="12" r="9" /><path d="m15 9-6 6" /><path d="m9 9 6 6" /></>);
export const IconReturnBox = icon(<><path d="M9 14 4 9l5-5" /><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" /></>);
export const IconIncoming = icon(<><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" /></>);
export const IconCertificate = icon(<><circle cx="12" cy="9" r="6" /><path d="M8.2 13.6 7 22l5-3 5 3-1.2-8.4" /></>);
export const IconSpec = icon(<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="m9 15 2 2 4-4" /></>);
export const IconRuler = icon(<><path d="M21.3 15.3 8.7 2.7a1 1 0 0 0-1.4 0L2.7 7.3a1 1 0 0 0 0 1.4l12.6 12.6a1 1 0 0 0 1.4 0l4.6-4.6a1 1 0 0 0 0-1.4z" /><path d="m7.5 10.5 2-2" /><path d="m10.5 13.5 2-2" /><path d="m13.5 16.5 2-2" /></>);
export const IconAlert = icon(<><path d="m10.3 3.9-8.2 14a2 2 0 0 0 1.7 3.1h16.4a2 2 0 0 0 1.7-3.1l-8.2-14a2 2 0 0 0-3.4 0z" /><path d="M12 9v4" /><path d="M12 17h.01" /></>);
export const IconWrench = icon(<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-7.9 7.9l-6.9 6.9a2.1 2.1 0 0 1-3-3l6.9-6.9a6 6 0 0 1 7.9-7.9z" />);

// ── shipping and procurement ───────────────────────────────────────────────────────────────────────────────────
export const IconShipment = icon(<><path d="M1 3h15v13H1z" /><path d="M16 8h4l3 3v5h-7" /><circle cx="5.5" cy="18.5" r="2.5" /><circle cx="18.5" cy="18.5" r="2.5" /></>);
export const IconReturnTruck = icon(<><path d="M9 14 4 9l5-5" /><path d="M20 20v-7a4 4 0 0 0-4-4H4" /></>);
export const IconSupplier = icon(<><path d="M3 21h18" /><path d="M5 21V7l8-4v18" /><path d="M19 21V11l-6-4" /><path d="M9 9v.01" /><path d="M9 12v.01" /><path d="M9 15v.01" /></>);
export const IconMaterial = icon(<><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5" /><path d="M3 12c0 1.7 4 3 9 3s9-1.3 9-3" /></>);
export const IconPurchase = icon(<><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" /><path d="M3 6h18" /><path d="M16 10a4 4 0 0 1-8 0" /></>);
/** The transport directory: an address book holding a truck (drivers, vehicles, carriers). */
export const IconTransportDirectory = icon(<><rect x="5" y="2" width="15" height="20" rx="2" /><path d="M3 7h3" /><path d="M3 12h3" /><path d="M3 17h3" />
  <path d="M8.5 8h5v5h-5z" /><path d="M13.5 10h2.2l1.3 1.6V13h-3.5" /><circle cx="10.2" cy="14.6" r="1.1" /><circle cx="15.2" cy="14.6" r="1.1" /></>);

export const IconReceipt = icon(<><path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 1 .7V2l-1 .7-3-2-3 2-3-2-3 2-3-2z" /><path d="M8 8h8" /><path d="M8 12h8" /><path d="M8 16h5" /></>);

// ── master data and administration ─────────────────────────────────────────────────────────────────────────────
export const IconProduct = icon(<><path d="m7.5 4.3 9 5.2" /><path d="M21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.7z" /><path d="M3.3 7 12 12l8.7-5" /><path d="M12 22V12" /></>);
export const IconGlobe = icon(<><circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 3a14 14 0 0 1 0 18" /><path d="M12 3a14 14 0 0 0 0 18" /></>);
export const IconBuilding = icon(<><rect x="4" y="2" width="16" height="20" rx="2" /><path d="M9 22v-4h6v4" /><path d="M8 6h.01" /><path d="M16 6h.01" /><path d="M8 10h.01" /><path d="M16 10h.01" /><path d="M8 14h.01" /><path d="M16 14h.01" /></>);
export const IconUser = icon(<><circle cx="12" cy="8" r="4" /><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1" /></>);
export const IconRoles = icon(<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="m9 12 2 2 4-4" /></>);
export const IconKeyRound = icon(<><circle cx="7.5" cy="15.5" r="5.5" /><path d="m21 2-9.6 9.6" /><path d="m15.5 7.5 3 3L22 7l-3-3" /></>);
export const IconHistory = icon(<><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /><path d="M12 7v5l4 2" /></>);
export const IconLock = icon(<><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></>);
export const IconActivity = icon(<path d="M22 12h-4l-3 9L9 3l-3 9H2" />);

/** The icon of each page in the sidebar, by its address. */
export const MENU_ICONS: Record<string, (props: IconProps) => ReactNode> = {
  "/customer-reports": IconReport, "/customers": IconCustomers, "/customer-interactions": IconChat, "/follow-ups": IconBell,
  "/complaints": IconComplaint, "/samples": IconFlask, "/quotes": IconQuote, "/commercial-orders": IconCart,
  "/workforce": IconBadge,
  "/commercial-dashboard": IconDashboard, "/quality-dashboard": IconDashboard, "/shipping-dashboard": IconDashboard, "/production": IconDashboard, "/work-centers": IconMachine, "/shifts": IconClock, "/shift-rosters": IconCrew, "/production/demands": IconInbox,
  "/production/planning": IconPlanning, "/production-orders": IconWorkOrder, "/production-results": IconBoxCheck, "/production-reports": IconReport,
  "/downtime-events": IconPause, "/waste-records": IconTrash,
  "/quality-checks": IconInspect, "/quality-rejections": IconReject, "/quality-returns": IconReturnBox, "/quality-incoming": IconIncoming,
  "/quality-certificates": IconCertificate, "/quality-specifications": IconSpec, "/quality-test-parameters": IconRuler, "/quality-reports": IconReport,
  "/shipments": IconShipment, "/shipment-returns": IconReturnTruck, "/shipping-directory": IconTransportDirectory,
  "/suppliers": IconSupplier, "/materials": IconMaterial, "/purchase-orders": IconPurchase, "/goods-receipts": IconReceipt,
  "/master-data/products": IconProduct, "/master-data/lists": IconGlobe, "/master-data/settings": IconSettings,
  "/non-conformance-reports": IconAlert, "/corrective-actions": IconWrench,
  "/admin/organization": IconBuilding, "/admin/users": IconUser, "/admin/roles": IconRoles, "/admin/permissions": IconKeyRound,
  "/admin/audit-log": IconHistory, "/admin/security-log": IconLock, "/admin/activity-log": IconActivity,
};
