"use client";

import { Breadcrumb, BreadcrumbItem } from "@carbon/react";
import {
  ArrowRight, Building, ChevronDown, Document, Identification,
  ImportExport, Location, Locked, Printer, Security, Settings, User, UserAdmin, UserMultiple,
} from "@carbon/icons-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import {
  ADMIN_NAV_GROUPS, adminDestination, administrationHome, canOpenAdminDestination,
  currentAdminDestination, findSettingsSection, type AdminDestination,
} from "@/lib/admin-navigation";
import { resetMainScroll } from "@/lib/reset-main-scroll";
import styles from "./administration.module.css";

const icons = {
  organisation: Building, settings: Settings, team: UserMultiple, roles: UserAdmin,
  company: Identification, documents: Document, locations: Location, operations: Settings,
  labels: Printer, integrations: ImportExport,
  mcp: Locked, audit: Security, profile: User,
} satisfies Record<AdminDestination, typeof Settings>;

export function AdminNavigation({ mobile = false }: { mobile?: boolean }) {
  const path = usePathname();
  const tab = useSearchParams().get("tab");
  const current = currentAdminDestination(path, tab);
  const { user } = useAuth();
  const mobileNav = useRef<HTMLDetailsElement>(null);
  const groups = ADMIN_NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((id) => canOpenAdminDestination(id, user)),
  })).filter((group) => group.items.length);

  function renderGroups() {
    return groups.map(({ label, items }) => (
      <div key={label} className={styles.navGroup}>
        <p className={styles.navLabel}>{label}</p>
        <ul aria-label={label}>
          {items.map((id) => {
            const destination = adminDestination(id);
            const Icon = icons[id];
            return (
              <li key={id}>
                <Link
                  href={destination.href}
                  onNavigate={() => { if (mobileNav.current) mobileNav.current.open = false; }}
                  aria-current={current === id ? "page" : undefined}
                  className={styles.navLink}
                >
                  <Icon size={16} aria-hidden="true" />
                  {destination.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    ));
  }

  if (mobile) {
    return (
      <details className={styles.mobileNav} ref={mobileNav}>
        <summary>Administration menu<ChevronDown size={16} aria-hidden="true" /></summary>
        <nav aria-label="Administration">{renderGroups()}</nav>
      </details>
    );
  }
  return (
    <nav className={styles.desktopNav} aria-label="Administration">
      <p className={styles.navTitle}>Administration</p>
      {renderGroups()}
    </nav>
  );
}

export function AdminBreadcrumb() {
  const path = usePathname();
  const tab = useSearchParams().get("tab");
  const { user } = useAuth();
  const current = currentAdminDestination(path, tab);
  const home = administrationHome(user);

  useEffect(() => {
    resetMainScroll();
  }, [path, tab]);

  if (!current) return null;
  const settingsPage = (path === "/settings" && findSettingsSection(tab)) || current === "mcp" || current === "integrations";
  const crumbs = [
    { label: "Administration", href: home === path && !tab ? undefined : home },
    ...(settingsPage ? [{ label: "Settings", href: "/settings" }] : []),
    ...(current === "mcp" ? [{ label: "Integrations", href: "/settings/integrations" }] : []),
    { label: adminDestination(current).label },
  ];

  return (
    <Breadcrumb noTrailingSlash className={`firstout-breadcrumb ${styles.breadcrumb}`} aria-label="Breadcrumb">
      {crumbs.map((crumb, index) => (
        <BreadcrumbItem key={crumb.label} isCurrentPage={index === crumbs.length - 1}>
          {crumb.href ? <Link href={crumb.href}>{crumb.label}</Link> : crumb.label}
        </BreadcrumbItem>
      ))}
    </Breadcrumb>
  );
}

export function AdminPageHeader({ title, description, children }: { title: string; description: string; children?: ReactNode }) {
  return (
    <header className={`firstout-page-header ${styles.pageHeader}`}>
      <div>
        <h1 className="cds--type-heading-06">{title}</h1>
        <p className="cds--type-body-01">{description}</p>
      </div>
      {children}
    </header>
  );
}

export function AdminDirectoryLinks({ items }: { items: readonly AdminDestination[] }) {
  const { user } = useAuth();
  return (
    <div className={styles.directory}>
      {items.filter((id) => canOpenAdminDestination(id, user)).map((id) => {
        const destination = adminDestination(id);
        const Icon = icons[id];
        return (
          <Link href={destination.href} className={`cds--tile cds--tile--clickable ${styles.directoryLink}`} key={id}>
            <Icon size={20} aria-hidden="true" />
            <span>
              <strong>{destination.label}</strong>
              <span>{destination.description}</span>
            </span>
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        );
      })}
    </div>
  );
}
