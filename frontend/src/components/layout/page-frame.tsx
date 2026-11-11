"use client";
import { CUSTOMER_REPORTS } from "@/features/reports/customer-permissions";

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { ProtectedRoute, useAuth, useHasAnyPermission } from "@/features/auth";
import { useCapaAlerts } from "@/features/ncr-reports/use-capa-alerts";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { API_BASE_URL } from "@/lib/api-client";
import side from "./sidebar.module.css";
import { MENU_ICONS } from "./menu-icons";
import {
  IconAlertTriangle,
  IconChevron,
  IconChevronUp,
  IconClipboardCheck,
  IconDelegation,
  IconFactory,
  IconGrid,
  IconIdCard,
  IconKey,
  IconLayers,
  IconBell,
  IconLogOut,
  IconMegaphone,
  IconMenu,
  IconShield,
  IconShieldCheck,
  IconTruck,
  IconPackage,
  IconUserCog,
  IconUsers,
  IconX,
} from "./nav-icons";
import { DEPARTMENTS } from "@/features/dashboard/departments";
import { DELEGATIONS_PAGE, useDelegationsWaiting } from "@/lib/delegations";
import { ANNOUNCEMENTS_PAGE } from "@/lib/notifications";
import { AcknowledgeGate, NotificationBell } from "@/components/notify/NotificationCenter";
import { P, PRODUCTION_REPORTS } from "@/lib/production-permissions";
import { Q, QUALITY_REPORTS } from "@/lib/quality-permissions";
import { S } from "@/lib/shipping-permissions";
import { PR } from "@/lib/procurement-permissions";
import { MD } from "@/lib/masterdata-permissions";

type PageFrameProps = {
  title: string;
  subtitle?: string;
  section?: string;
  action?: ReactNode;
  children: ReactNode;
};

type NavIcon = (props: { size?: number }) => ReactNode;

type StaticNavLink = {
  href: string;
  labelKey: string;
  permission?: string;
  anyPermissions?: string[];
  icon?: NavIcon;
  // A count next to the link of what needs the user's attention there.
  badge?: "capa" | "delegations";
};

type StaticNavGroup = {
  labelKey: string;
  icon: NavIcon;
  links: StaticNavLink[];
};

const styles: Record<string, CSSProperties> = {
  sidebar: {
    display: "flex",
    flexDirection: "column",
  },
  page: {
    color: "var(--text)",
    fontFamily: "inherit",
    padding: "24px 32px 40px",
  },
  contentTop: {
    alignItems: "center",
    display: "flex",
    gap: "12px",
    marginBottom: "8px",
  },
  hamburgerButton: {
    alignItems: "center",
    background: "none",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    color: "var(--text)",
    cursor: "pointer",
    display: "flex",
    height: "36px",
    justifyContent: "center",
    width: "36px",
  },
  header: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: "16px",
    marginBottom: "24px",
  },
  eyebrow: {
    margin: "0 0 8px",
    color: "var(--text-muted)",
    fontSize: "14px",
    fontWeight: 700,
  },
  title: {
    margin: 0,
    fontSize: "28px",
    lineHeight: 1.2,
  },
  subtitle: {
    margin: "8px 0 0",
    color: "var(--text-muted)",
    lineHeight: 1.5,
  },
};

// Which sections of the sidebar the user folded or unfolded (kept in this browser only).
const SIDEBAR_GROUPS_KEY = "iorp.sidebar.groups";

const staticNavGroups: StaticNavGroup[] = [
  {
    labelKey: "sections.commercial",
    icon: IconUsers,
    links: [
      { href: "/commercial-dashboard", labelKey: "links.commercialDashboard", anyPermissions: [...DEPARTMENTS.find(d => d.key === "commercial")!.permissions] },
      { href: "/customer-reports", labelKey: "links.customerReports", anyPermissions: CUSTOMER_REPORTS },
      { href: "/customers", labelKey: "links.customers", permission: "commercial:customers:read" },
      { href: "/customer-interactions", labelKey: "links.customerInteractions", permission: "commercial:interactions:read" },
      { href: "/follow-ups", labelKey: "links.followUps", permission: "commercial:follow_ups:read" },
      { href: "/complaints", labelKey: "links.complaints", permission: "commercial:complaints:read" },
      { href: "/samples", labelKey: "links.samples", permission: "commercial:samples:read" },
      { href: "/quotes", labelKey: "links.quotes", permission: "commercial:quotes:read" },
      { href: "/commercial-orders", labelKey: "links.commercialOrders", permission: "commercial:orders:read" },
    ],
  },
  {
    labelKey: "sections.workforce",
    icon: IconIdCard,
    links: [
      { href: "/workforce", labelKey: "links.workforceMembers", permission: "workforce:members:read" },
    ],
  },
  {
    labelKey: "sections.production",
    icon: IconFactory,
    links: [
      // DASH-001: the section opens on its own dashboard.
      { href: "/production", labelKey: "links.productionDashboard", anyPermissions: [P.ORDERS_READ, P.RESULTS_READ, P.DOWNTIME_READ, P.DEMANDS_READ] },
      { href: "/work-centers", labelKey: "links.workCenters", permission: P.WORK_CENTERS_READ },
      { href: "/shifts", labelKey: "links.shifts", permission: P.SHIFTS_READ },
      { href: "/shift-rosters", labelKey: "links.shiftRosters", permission: P.ROSTERS_READ },
      { href: "/production/demands", labelKey: "links.demands", permission: P.DEMANDS_READ },
      { href: "/production/planning", labelKey: "links.planning", permission: P.PLANNING_READ },
      { href: "/production-orders", labelKey: "links.productionOrders", permission: P.ORDERS_READ },
      // The final result of completed and closed orders.
      { href: "/production-results", labelKey: "links.productionOutputs", permission: P.RESULTS_READ },
      { href: "/production-reports", labelKey: "links.productionReports", anyPermissions: PRODUCTION_REPORTS },
      { href: "/downtime-events", labelKey: "links.downtimeEvents", permission: P.DOWNTIME_READ },
      { href: "/waste-records", labelKey: "links.wasteRecords", permission: P.WASTE_READ },
    ],
  },
  {
    labelKey: "sections.quality",
    icon: IconClipboardCheck,
    links: [
      { href: "/quality-dashboard", labelKey: "links.qualityDashboard", anyPermissions: [...DEPARTMENTS.find(d => d.key === "quality")!.permissions] },
      { href: "/quality-checks", labelKey: "links.qualityChecks", permission: Q.CHECKS_READ },
      { href: "/quality-rejections", labelKey: "links.qualityRejections", permission: Q.REJECTIONS_READ },
      { href: "/quality-returns", labelKey: "links.qualityReturns", permission: Q.CHECKS_READ },
      { href: "/quality-incoming", labelKey: "links.qualityIncoming", permission: Q.CHECKS_READ },
      { href: "/quality-certificates", labelKey: "links.qualityCertificates", permission: Q.COA_READ },
      { href: "/quality-specifications", labelKey: "links.qualitySpecifications", permission: Q.SPECS_READ },
      { href: "/quality-test-parameters", labelKey: "links.qualityTestParameters", permission: Q.SPECS_READ },
      { href: "/quality-reports", labelKey: "links.qualityReports", anyPermissions: QUALITY_REPORTS },
    ],
  },
  {
    labelKey: "sections.shipping",
    icon: IconTruck,
    links: [
      { href: "/shipping-dashboard", labelKey: "links.shippingDashboard", anyPermissions: [...DEPARTMENTS.find(d => d.key === "shipping")!.permissions] },
      { href: "/shipments", labelKey: "links.shipments", permission: S.SHIPMENTS_READ },
      { href: "/shipment-returns", labelKey: "links.shipmentReturns", permission: S.RETURNS_READ },
    ],
  },
  {
    labelKey: "sections.procurement",
    icon: IconPackage,
    links: [
      { href: "/procurement-dashboard", labelKey: "links.procurementDashboard", anyPermissions: [...DEPARTMENTS.find(d => d.key === "procurement")!.permissions] },
      { href: "/suppliers", labelKey: "links.suppliers", permission: PR.SUPPLIERS_READ },
      { href: "/materials", labelKey: "links.materials", permission: PR.MATERIALS_READ },
      { href: "/purchase-orders", labelKey: "links.purchaseOrders", permission: PR.PO_READ },
      { href: "/goods-receipts", labelKey: "links.goodsReceipts", permission: PR.RECEIPTS_READ },
    ],
  },
  {
    // MD-001: the organization's products and general settings, used by every module (owned by master data).
    labelKey: "sections.masterData",
    icon: IconLayers,
    links: [
      { href: "/master-data/products", labelKey: "links.products", permission: MD.PRODUCTS_READ },
      { href: "/master-data/lists", labelKey: "links.referenceLists", permission: MD.LISTS_READ },
      { href: "/shipping-directory", labelKey: "links.transportDirectory", permission: "shipping:directory:read" },
      { href: "/master-data/settings", labelKey: "links.generalSettings", permission: MD.SETTINGS_READ },
    ],
  },
  {
    labelKey: "sections.ncr",
    icon: IconAlertTriangle,
    links: [
      { href: "/non-conformance-reports", labelKey: "links.ncrReports", permission: Q.NCR_READ },
    ],
  },
  {
    labelKey: "sections.capa",
    icon: IconShieldCheck,
    links: [
      { href: "/corrective-actions", labelKey: "links.correctiveActions", anyPermissions: [Q.NCR_ACTIONS_READ, Q.NCR_READ], badge: "capa" },
    ],
  },
];

function isLinkActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function useOrganizationLogoSrc(logoUrl: string | null | undefined, token: string | null): string | null {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!logoUrl || !token) {
      setSrc(null);
      return;
    }
    let objectUrl: string | null = null;
    let cancelled = false;

    fetch(`${API_BASE_URL}${logoUrl}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => (response.ok ? response.blob() : null))
      .then((blob) => {
        if (cancelled || !blob) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => setSrc(null));

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [logoUrl, token]);

  return src;
}

export function PageFrame({ title, subtitle, section, action, children }: PageFrameProps) {
  const { user, token, hasPermission, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations("navigation");
  const [mobileOpen, setMobileOpen] = useState(false);
  const logoSrc = useOrganizationLogoSrc(user?.organization_logo_url, token);
  const canManageUsers = useHasAnyPermission([
    "foundation:organization:read",
    "organization:branding:read",
    "foundation:users:read",
    "foundation:roles:read",
    "foundation:permissions:read",
    ...DELEGATIONS_PAGE,  // a holder of any approval delegates it from here
    ...ANNOUNCEMENTS_PAGE,  // who writes announcements follows them from here
  ]);

  const [menuOpen, setMenuOpen] = useState(false);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const [groupsLoaded, setGroupsLoaded] = useState(false);
  const sidebarRef = useRef<HTMLElement>(null);
  const restoredSidebar = useRef<{ element: HTMLElement; pathname: string; mobileOpen: boolean } | null>(null);
  const footerRef = useRef<HTMLDivElement>(null);

  // Read after the first render, so the server's page and the browser's match.
  useLayoutEffect(() => {
    try { setOpenGroups(JSON.parse(window.localStorage.getItem(SIDEBAR_GROUPS_KEY) ?? "{}")); } catch { /* nothing remembered */ }
    setGroupsLoaded(true);
  }, []);

  // Restore after remembered groups have expanded, before paint. The same nav
  // scroll container is used by desktop and the mobile drawer.
  useLayoutEffect(() => {
    const element = sidebarRef.current;
    if (!groupsLoaded || !element || element.clientHeight === 0) return;
    const previous = restoredSidebar.current;
    if (previous?.element === element && previous.pathname === pathname && previous.mobileOpen === mobileOpen) return;
    restoredSidebar.current = { element, pathname, mobileOpen };
    try {
      const remembered = Number(window.sessionStorage.getItem("iorp.sidebar.scroll"));
      if (Number.isFinite(remembered) && remembered >= 0) element.scrollTop = remembered;
    } catch { /* storage can be disabled */ }
    const active = element.querySelector<HTMLElement>('[aria-current="page"]');
    if (!active) return;
    const viewport = element.getBoundingClientRect();
    const item = active.getBoundingClientRect();
    if (item.height > 0 && (item.top < viewport.top || item.bottom > viewport.bottom)) {
      active.scrollIntoView?.({ block: "nearest" });
    }
  }); // ProtectedRoute can mount the nav on a later commit; the ref prevents repeated scrolling.

  function rememberSidebarScroll() {
    try { window.sessionStorage.setItem("iorp.sidebar.scroll", String(sidebarRef.current?.scrollTop ?? 0)); }
    catch { /* private mode: retain navigation without persistence */ }
  }

  // The user's menu closes with Escape or a click elsewhere.
  useEffect(() => {
    if (!menuOpen) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !footerRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); };
  }, [menuOpen]);

  useEffect(() => {
    setMobileOpen(false);
    setMenuOpen(false);
  }, [pathname]);

  function toggleGroup(key: string, open: boolean) {
    setOpenGroups((current) => {
      const next = { ...current, [key]: open };
      try { window.localStorage.setItem(SIDEBAR_GROUPS_KEY, JSON.stringify(next)); } catch { /* private mode: just this visit */ }
      return next;
    });
  }
  const capaAlerts = useCapaAlerts(hasPermission(Q.NCR_ACTIONS_READ) || hasPermission(Q.NCR_READ));
  const canDelegate = useHasAnyPermission(DELEGATIONS_PAGE);
  const delegationsWaiting = useDelegationsWaiting(canDelegate);
  const badges: Record<string, number> = { capa: capaAlerts?.total ?? 0, delegations: delegationsWaiting };

  const visibleStaticNavGroups = staticNavGroups
    .map((group) => ({
      ...group,
      links: group.links.filter(
        (link) => (!link.permission || hasPermission(link.permission)) && (!link.anyPermissions || link.anyPermissions.some(hasPermission)),
      ),
    }))
    .filter((group) => group.links.length > 0);

  const navGroups: StaticNavGroup[] = canManageUsers
    ? [
        ...visibleStaticNavGroups,
        {
          labelKey: "sections.administration",
          icon: IconUserCog,
          links: [
            ...(hasPermission("foundation:organization:read") || hasPermission("organization:branding:read")
              ? [{ href: "/admin/organization", labelKey: "links.organizationSettings", icon: IconFactory }]
              : []),
            ...(hasPermission("foundation:users:read")
              ? [{ href: "/admin/users", labelKey: "links.adminUsers", icon: IconUserCog }]
              : []),
            ...(hasPermission("foundation:roles:read")
              ? [{ href: "/admin/roles", labelKey: "links.adminRoles", icon: IconShield }]
              : []),
            ...(hasPermission("foundation:permissions:read")
              ? [{ href: "/admin/permissions", labelKey: "links.adminPermissions", icon: IconKey }]
              : []),
            ...(canDelegate
              ? [{ href: "/admin/delegations", labelKey: "links.delegations", icon: IconDelegation, badge: "delegations" as const }]
              : []),
            ...(ANNOUNCEMENTS_PAGE.some(hasPermission)
              ? [{ href: "/admin/announcements", labelKey: "links.announcements", icon: IconMegaphone }]
              : []),
            ...(hasPermission("foundation:audit:read")
              ? [{ href: "/admin/audit-log", labelKey: "links.auditLog", icon: IconClipboardCheck }]
              : []),
            ...(hasPermission("foundation:security_log:read")
              ? [{ href: "/admin/security-log", labelKey: "links.securityLog", icon: IconKey }]
              : []),
            ...(hasPermission("foundation:activity_log:read")
              ? [{ href: "/admin/activity-log", labelKey: "links.activityLog", icon: IconClipboardCheck }]
              : []),
          ],
        },
      ]
    : visibleStaticNavGroups;

  function handleSignOut() {
    logout();
    router.replace("/login");
  }

  const initials = (user?.full_name ?? "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "?";

  return (
    <ProtectedRoute>
      <div className="iorp-shell">
        <aside
          className={`iorp-sidebar${mobileOpen ? " iorp-sidebar-open" : ""}`}
          style={styles.sidebar}
          aria-label={t("dashboard")}
        >
          <div className={side.brand}>
            <span className={side.mark}>
              {logoSrc ? <img src={logoSrc} alt="" /> : (user?.organization_name ?? "?").slice(0, 1).toUpperCase()}
            </span>
            <span className={`iorp-brand-text ${side.brandText}`}>
              <p className={side.appName}>{t("appName")}</p>
              <p className={side.orgName}>{user?.organization_name ?? ""}</p>
            </span>
          </div>

          <nav className="iorp-sidebar-nav" ref={sidebarRef} onScroll={rememberSidebarScroll}>
            <Link href="/dashboard" className={`iorp-nav-link ${side.link} ${side.home} ${isLinkActive(pathname, "/dashboard") ? side.active : ""}`}
              title={t("dashboard")} aria-current={isLinkActive(pathname, "/dashboard") ? "page" : undefined}>
              <IconGrid size={19} />
              <span className="iorp-nav-label">{t("dashboard")}</span>
            </Link>

            {navGroups.map((group) => {
              const GroupIcon = group.icon;
              const current = group.links.some((link) => isLinkActive(pathname, link.href));
              const open = openGroups[group.labelKey] ?? current;
              const groupBadge = group.links.reduce((sum, link) => sum + (link.badge ? badges[link.badge] ?? 0 : 0), 0);
              return (
                <div key={group.labelKey} className={`${side.group} ${open ? side.open : side.closed}`}>
                  <button type="button" className={`${side.groupHead} ${current ? side.groupCurrent : ""}`} aria-expanded={open}
                    title={t(group.labelKey)} onClick={() => toggleGroup(group.labelKey, !open)}>
                    <GroupIcon size={18} />
                    <span className="iorp-nav-label iorp-section-label">{t(group.labelKey)}</span>
                    {!open && groupBadge > 0 ? <span className={`iorp-nav-label ${side.badge}`}>{groupBadge}</span> : null}
                    <span className={`iorp-nav-label ${side.chevron}`}><IconChevron size={15} /></span>
                  </button>
                  <div className={side.groupLinks}>
                    {group.links.map((link) => {
                      const LinkIcon = MENU_ICONS[link.href] ?? link.icon;
                      const active = isLinkActive(pathname, link.href);
                      return (
                        <Link key={link.href} href={link.href} className={`iorp-nav-link ${side.link} ${active ? side.active : ""}`}
                          title={t(link.labelKey)} aria-current={active ? "page" : undefined}>
                          {LinkIcon ? <LinkIcon size={17} /> : <span className={side.bullet} />}
                          <span className="iorp-nav-label">{t(link.labelKey)}</span>
                          {link.badge && badges[link.badge] > 0 && <span className={`iorp-nav-label ${side.badge}`}
                            aria-label={t("needsAttention", { count: badges[link.badge] })}>{badges[link.badge]}</span>}
                        </Link>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </nav>

          <div className={side.footer} ref={footerRef}>
            {menuOpen ? (
              <div className={side.menu} role="menu" aria-label={t("userMenu.label")}>
                <Link href="/admin/profile" className={side.menuItem} role="menuitem"><IconIdCard size={16} />{t("userMenu.profile")}</Link>
                <Link href="/admin/change-password" className={side.menuItem} role="menuitem"><IconKey size={16} />{t("userMenu.changePassword")}</Link>
                <Link href="/admin/sessions" className={side.menuItem} role="menuitem"><IconShield size={16} />{t("userMenu.sessions")}</Link>
                <Link href="/notifications" className={side.menuItem} role="menuitem"><IconBell size={16} />{t("links.notifications")}</Link>
                <div className={side.menuDivider} />
                <div className={side.menuSetting}><LanguageSwitcher label={t("language")} /></div>
                <div className={side.menuSetting}><ThemeToggle /></div>
                <div className={side.menuDivider} />
                <button type="button" className={`${side.menuItem} ${side.menuDanger}`} role="menuitem" onClick={handleSignOut}>
                  <IconLogOut size={16} />{t("userMenu.logout")}
                </button>
              </div>
            ) : null}
            <button type="button" className={`${side.userCard} ${menuOpen ? side.userCardOpen : ""}`} aria-expanded={menuOpen} aria-haspopup="menu"
              onClick={() => setMenuOpen((open) => !open)} title={user?.full_name}>
              <span className={side.avatar}>{initials}</span>
              <span className={`iorp-user-details ${side.userText}`}>
                <p className={side.userName}>{user?.full_name}</p>
                <p className={side.userRole}>{user?.roles?.[0] ?? ""}</p>
              </span>
              <span className={`iorp-nav-label ${side.caret}`}><IconChevronUp size={16} /></span>
            </button>
          </div>
        </aside>

        <button
          type="button"
          className={`iorp-backdrop${mobileOpen ? " iorp-backdrop-open" : ""}`}
          aria-label={t("dashboard")}
          onClick={() => setMobileOpen(false)}
        />

        <div className="iorp-content">
          <main style={styles.page}>
            <div style={styles.contentTop}>
              <button
                type="button"
                className="iorp-hamburger iorp-icon-button"
                style={styles.hamburgerButton}
                onClick={() => setMobileOpen((open) => !open)}
                aria-label={t("dashboard")}
              >
                {mobileOpen ? <IconX size={18} /> : <IconMenu size={18} />}
              </button>
              <NotificationBell />
            </div>
            <AcknowledgeGate />
            <header style={styles.header}>
              <div style={{ minInlineSize: 0, maxInlineSize: "100%" }}>
                <p style={styles.eyebrow}>{formatSectionLabel(section, t)}</p>
                <h1 style={styles.title}>{title}</h1>
                {subtitle ? <p style={styles.subtitle}>{subtitle}</p> : null}
              </div>
              {action}
            </header>
            {children}
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
}

function formatSectionLabel(section: string | undefined, t: (key: string) => string) {
  const sectionKeys: Record<string, string> = {
    IORP: "sections.iorp",
    Commercial: "sections.commercial",
    Workforce: "sections.workforce",
    Production: "sections.production",
    Quality: "sections.quality",
    NCR: "sections.ncr",
    CAPA: "sections.capa",
    Administration: "sections.administration",
  };

  return t(sectionKeys[section ?? "Commercial"] ?? "sections.commercial");
}
