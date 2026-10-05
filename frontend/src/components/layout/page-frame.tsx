"use client";
import { CUSTOMER_REPORTS } from "@/features/reports/customer-permissions";

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { ProtectedRoute, useAuth, useHasAnyPermission } from "@/features/auth";
import { useCapaAlerts } from "@/features/ncr-reports/use-capa-alerts";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { API_BASE_URL } from "@/lib/api-client";
import {
  IconAlertTriangle,
  IconClipboardCheck,
  IconFactory,
  IconGrid,
  IconIdCard,
  IconKey,
  IconLogOut,
  IconMenu,
  IconShield,
  IconShieldCheck,
  IconTruck,
  IconPackage,
  IconUserCog,
  IconUsers,
  IconX,
} from "./nav-icons";
import { P, PRODUCTION_REPORTS } from "@/lib/production-permissions";
import { Q, QUALITY_REPORTS } from "@/lib/quality-permissions";
import { S } from "@/lib/shipping-permissions";
import { PR } from "@/lib/procurement-permissions";

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
  badge?: "capa";
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
  brand: {
    alignItems: "center",
    display: "flex",
    gap: "10px",
    padding: "18px 16px",
    borderBottom: "1px solid var(--border)",
  },
  brandMark: {
    alignItems: "center",
    background: "var(--text)",
    borderRadius: "8px",
    color: "var(--surface)",
    display: "flex",
    flexShrink: 0,
    fontSize: "14px",
    fontWeight: 800,
    height: "34px",
    justifyContent: "center",
    overflow: "hidden",
    width: "34px",
  },
  brandMarkImage: {
    height: "100%",
    objectFit: "cover",
    width: "100%",
  },
  brandText: {
    minWidth: 0,
  },
  brandName: {
    fontSize: "15px",
    fontWeight: 800,
    margin: 0,
    whiteSpace: "nowrap",
  },
  brandOrg: {
    color: "var(--text-muted)",
    fontSize: "12px",
    margin: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  navSection: {
    marginBottom: "6px",
  },
  navSectionHeader: {
    alignItems: "center",
    color: "var(--text-subtle)",
    display: "flex",
    fontSize: "11px",
    fontWeight: 800,
    gap: "8px",
    letterSpacing: "0.06em",
    padding: "10px 10px 6px",
    textTransform: "uppercase",
  },
  navLink: {
    alignItems: "center",
    borderRadius: "8px",
    color: "var(--text-muted)",
    display: "flex",
    fontSize: "13.5px",
    fontWeight: 600,
    gap: "10px",
    margin: "1px 0",
    padding: "9px 10px",
    textDecoration: "none",
  },
  navLinkActive: {
    background: "var(--accent-soft)",
    color: "var(--accent-strong)",
  },
  navBadge: {
    background: "var(--danger)",
    borderRadius: "999px",
    color: "var(--on-accent)",
    fontSize: "11px",
    fontWeight: 700,
    lineHeight: "18px",
    marginInlineStart: "auto",
    minWidth: "18px",
    padding: "0 6px",
    textAlign: "center",
  },
  navBullet: {
    background: "currentColor",
    borderRadius: "999px",
    flexShrink: 0,
    height: "5px",
    opacity: 0.55,
    width: "5px",
  },
  navDashboardLink: {
    alignItems: "center",
    borderRadius: "8px",
    color: "var(--text)",
    display: "flex",
    fontSize: "14px",
    fontWeight: 800,
    gap: "10px",
    margin: "8px 0 10px",
    padding: "9px 10px",
    textDecoration: "none",
  },
  sidebarFooter: {
    borderTop: "1px solid var(--border)",
    display: "grid",
    gap: "10px",
    padding: "14px 16px",
  },
  userRow: {
    alignItems: "center",
    display: "flex",
    gap: "10px",
  },
  avatar: {
    alignItems: "center",
    background: "var(--accent-soft)",
    borderRadius: "999px",
    color: "var(--accent-strong)",
    display: "flex",
    flexShrink: 0,
    fontSize: "13px",
    fontWeight: 800,
    height: "32px",
    justifyContent: "center",
    width: "32px",
  },
  userDetails: {
    minWidth: 0,
  },
  userName: {
    fontSize: "13px",
    fontWeight: 700,
    margin: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  userRole: {
    color: "var(--text-subtle)",
    fontSize: "11.5px",
    margin: 0,
    textTransform: "capitalize",
  },
  logoutButton: {
    alignItems: "center",
    background: "none",
    border: "1px solid var(--border)",
    borderRadius: "8px",
    color: "var(--text-muted)",
    cursor: "pointer",
    display: "flex",
    fontSize: "13px",
    fontWeight: 700,
    gap: "8px",
    justifyContent: "center",
    padding: "8px 10px",
  },
  page: {
    color: "var(--text)",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
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

const staticNavGroups: StaticNavGroup[] = [
  {
    labelKey: "sections.commercial",
    icon: IconUsers,
    links: [
      { href: "/customer-reports", labelKey: "links.customerReports", anyPermissions: CUSTOMER_REPORTS },
      { href: "/customers", labelKey: "links.customers", permission: "commercial:customers:read" },
      { href: "/customer-interactions", labelKey: "links.customerInteractions", permission: "commercial:interactions:read" },
      { href: "/follow-ups", labelKey: "links.followUps", permission: "commercial:follow_ups:read" },
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
      { href: "/shipments", labelKey: "links.shipments", permission: S.SHIPMENTS_READ },
      { href: "/shipment-returns", labelKey: "links.shipmentReturns", permission: S.RETURNS_READ },
    ],
  },
  {
    labelKey: "sections.procurement",
    icon: IconPackage,
    links: [
      { href: "/suppliers", labelKey: "links.suppliers", permission: PR.SUPPLIERS_READ },
      { href: "/materials", labelKey: "links.materials", permission: PR.MATERIALS_READ },
      { href: "/goods-receipts", labelKey: "links.goodsReceipts", permission: PR.RECEIPTS_READ },
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
  ]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);
  const capaAlerts = useCapaAlerts(hasPermission(Q.NCR_ACTIONS_READ) || hasPermission(Q.NCR_READ));
  const badges: Record<string, number> = { capa: capaAlerts?.total ?? 0 };

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
          <div style={styles.brand}>
            <span style={styles.brandMark}>
              {logoSrc ? (
                <img src={logoSrc} alt="" style={styles.brandMarkImage} />
              ) : (
                (user?.organization_name ?? "?").slice(0, 1).toUpperCase()
              )}
            </span>
            <span className="iorp-brand-text" style={styles.brandText}>
              <p style={styles.brandName}>{t("appName")}</p>
              <p style={styles.brandOrg}>{user?.organization_name ?? ""}</p>
            </span>
          </div>

          <nav className="iorp-sidebar-nav">
            <Link
              href="/dashboard"
              style={{
                ...styles.navDashboardLink,
                ...(isLinkActive(pathname, "/dashboard") ? styles.navLinkActive : {}),
              }}
            >
              <IconGrid size={18} />
              <span className="iorp-nav-label">{t("dashboard")}</span>
            </Link>

            {navGroups.map((group) => {
              const GroupIcon = group.icon;
              return (
                <div key={group.labelKey} style={styles.navSection}>
                  <div style={styles.navSectionHeader}>
                    <GroupIcon size={14} />
                    <span className="iorp-nav-label iorp-section-label">{t(group.labelKey)}</span>
                  </div>
                  {group.links.map((link) => {
                    const LinkIcon = link.icon;
                    const active = isLinkActive(pathname, link.href);
                    return (
                      <Link
                        key={link.href}
                        href={link.href}
                        className="iorp-nav-link"
                        style={{
                          ...styles.navLink,
                          ...(active ? styles.navLinkActive : {}),
                        }}
                        title={t(link.labelKey)}
                      >
                        {LinkIcon ? <LinkIcon size={16} /> : <span style={styles.navBullet} />}
                        <span className="iorp-nav-label">{t(link.labelKey)}</span>
                        {link.badge && badges[link.badge] > 0 && <span className="iorp-nav-label" style={styles.navBadge}
                          aria-label={t("needsAttention", { count: badges[link.badge] })}>{badges[link.badge]}</span>}
                      </Link>
                    );
                  })}
                </div>
              );
            })}
          </nav>

          <div style={styles.sidebarFooter}>
            <div style={styles.userRow}>
              <span style={styles.avatar}>{initials}</span>
              <span className="iorp-user-details" style={styles.userDetails}>
                <p style={styles.userName}>{user?.full_name}</p>
                <p style={styles.userRole}>{user?.roles?.[0] ?? ""}</p>
              </span>
            </div>
            <LanguageSwitcher label={t("language")} />
            <ThemeToggle />
            <Link href="/admin/profile" style={styles.logoutButton}>
              <IconIdCard size={16} />
              <span className="iorp-nav-label">{t("userMenu.profile")}</span>
            </Link>
            <Link href="/admin/change-password" style={styles.logoutButton}>
              <IconKey size={16} />
              <span className="iorp-nav-label">{t("userMenu.changePassword")}</span>
            </Link>
            <button type="button" style={styles.logoutButton} onClick={handleSignOut}>
              <IconLogOut size={16} />
              <span className="iorp-nav-label">{t("userMenu.logout")}</span>
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
            </div>
            <header style={styles.header}>
              <div>
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
