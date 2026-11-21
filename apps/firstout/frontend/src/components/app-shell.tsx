"use client";

import {
  Header,
  HeaderGlobalAction,
  HeaderGlobalBar,
  HeaderMenuButton,
  HeaderName,
  SideNav,
  SideNavItems,
  SideNavLink,
  SideNavMenu,
  SideNavMenuItem,
  SkipToContent,
  SkeletonPlaceholder,
  SkeletonText,
  Theme,
} from "@carbon/react";
import {
  Barcode,
  Calendar,
  Catalog,
  Delivery,
  DeliveryParcel,
  DeliveryTruck,
  Document,
  DocumentImport,
  Finance,
  Home,
  Industry,
  InventoryManagement,
  Location,
  Logout,
  Money,
  Movement,
  Notebook,
  PiggyBank,
  Product,
  Purchase,
  Receipt,
  Renew,
  Report,
  Settings,
  ShoppingCart,
  Store,
  Task,
  Undo,
  User,
  UserAdmin,
  UserFollow,
  UserMultiple,
  Wallet,
  ChartLine,
  Currency,
  DocumentSubtract,
  Security,
  DocumentTasks,
} from "@carbon/icons-react";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, useState, useSyncExternalStore, type MouseEvent, type ReactNode } from "react";

import { StaffOrganizationSwitcher, useStaffSession } from "@/components/staff-provider";
import { isPublicAuthPath, missingSessionDestination } from "@/lib/auth-routes";
import { useAuth } from "@/lib/auth";
import { resetMainScroll } from "@/lib/reset-main-scroll";
import { can } from "@/lib/permissions";
import {
  BOOKS_NAV_ITEMS,
  CATALOGUE_NAV_ITEMS,
  HOME_NAV_ITEM,
  SALES_NAV_ITEMS,
  STOCK_NAV_ITEMS,
  TILL_NAV_ITEM,
  WAREHOUSE_NAV_ITEMS,
  isAdminPath,
  isBooksPath,
  isCatalogueMenuPath,
  isNavLinkActive,
  isSalesPath,
  isStockPath,
  isWarehousePath,
} from "@/lib/nav";
import { AppBreadcrumb } from "@/components/app-breadcrumb";
import { AdminBreadcrumb, AdminNavigation } from "@/components/administration";
import adminStyles from "@/components/administration.module.css";
import { administrationHome } from "@/lib/admin-navigation";
import { PageLoading } from "@/components/page-loading";
import loadingStyles from "@/components/auth-loading.module.css";
import { HeaderSearch } from "@/components/header-search";
import {
  getNarrowViewportServerSnapshot,
  getNarrowViewportSnapshot,
  subscribeNarrowViewport,
} from "@/lib/viewport";
import {
  getSideNavExpandedServerSnapshot,
  getSideNavExpandedSnapshot,
  setSideNavExpanded,
  subscribeSideNavExpanded,
  toggleSideNavExpanded,
} from "@/lib/side-nav-preference";

const ICONS = {
  "/": Home,
  "/locations": Location,
  "/suppliers": Industry,
  "/price-lists": Currency,
  "/proformas": Document,
  "/catalogue": Catalog,
  "/stocktakes": InventoryManagement,
  "/adjustments": Report,
  "/import": DocumentImport,
  "/reorder": ShoppingCart,
  "/purchase-orders": Purchase,
  "/transit": Delivery,
  "/receive": DeliveryParcel,
  "/wms": Barcode,
  "/transfers": Movement,
  "/picks": Task,
  "/deliveries": DeliveryTruck,
  "/returns": Undo,
  "/quotes": Document,
  "/orders": Receipt,
  "/laybys": PiggyBank,
  "/customers": UserFollow,
  "/ledger": Finance,
  "/journals": Notebook,
  "/invoices": Receipt,
  "/repeating-invoices": Renew,
  "/credit-notes": DocumentSubtract,
  "/bills": Purchase,
  "/payments": Wallet,
  "/bank-reconciliation": DocumentTasks,
  "/reports": ChartLine,
  "/vat201": Document,
  "/books-periods": Calendar,
  "/till": Money,
  "/audit": Security,
  "/users": UserMultiple,
  "/roles": UserAdmin,
  "/profile": User,
  "/settings": Settings,
  "/organisation": UserAdmin,
} as const;

type NavHref = keyof typeof ICONS;

function navIcon(href: string) {
  return ICONS[href as NavHref];
}

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const { signedIn: clerkSignedIn } = useStaffSession();
  const workspaceNavExpanded = useSyncExternalStore(
    subscribeSideNavExpanded,
    getSideNavExpandedSnapshot,
    getSideNavExpandedServerSnapshot,
  );
  const narrow = useSyncExternalStore(
    subscribeNarrowViewport,
    getNarrowViewportSnapshot,
    getNarrowViewportServerSnapshot,
  );
  const isPublic = isPublicAuthPath(pathname);
  const isAdministration = !loading && isAdminPath(pathname);
  const [adminNavExpanded, setAdminNavExpanded] = useState(false);
  const expanded = isAdministration ? adminNavExpanded : workspaceNavExpanded;

  function closeNav() {
    setAdminNavExpanded(false);
    if (!isAdministration) setSideNavExpanded(false);
  }

  function toggleNav() {
    if (isAdministration) setAdminNavExpanded((open) => !open);
    else toggleSideNavExpanded();
  }

  useEffect(() => {
    if (!loading && !user && !isPublic) {
      router.replace(missingSessionDestination(clerkSignedIn));
    }
  }, [loading, user, isPublic, clerkSignedIn, router]);

  useEffect(() => {
    if (narrow) {
      setSideNavExpanded(false);
    }
  }, [narrow]);

  // Pathname tab changes must reset document/main scroll so the fixed header
  // does not clip page titles / primary actions from a prior scrolled page.
  // rAF: run after Next scroll restoration / layout paint.
  useEffect(() => {
    if (isPublic) {
      return;
    }
    resetMainScroll();
    const id = requestAnimationFrame(() => resetMainScroll());
    return () => cancelAnimationFrame(id);
  }, [pathname, isPublic]);

  if (isPublic) {
    return <>{children}</>;
  }

  if (!loading && !user) return null;

  const salesNavItems = can(user, "sales.refunds") && !can(user, "sales.orders")
    ? SALES_NAV_ITEMS.filter((item) => item.href === "/orders")
    : SALES_NAV_ITEMS;
  // Commission is gated like GET /reports/commission (books.mutate or users.manage).
  const booksNavItems = can(user, "books.mutate") || can(user, "users.manage")
    ? BOOKS_NAV_ITEMS
    : BOOKS_NAV_ITEMS.filter((item) => item.href !== "/commission");

  function renderNavMenu(
    title: string,
    icon: typeof Product,
    pathActive: boolean,
    items: ReadonlyArray<{ href: string; label: string; mobileOnly?: boolean }>,
    keyPrefix: string,
  ) {
    return (
      <SideNavMenu
        key={pathActive ? `${keyPrefix}-open` : `${keyPrefix}-closed`}
        renderIcon={icon}
        title={title}
        defaultExpanded={pathActive}
        isActive={pathActive}
      >
        {items.map((item) => (
          <SideNavMenuItem
            key={item.href}
            href={item.href}
            className={item.mobileOnly ? "firstout-nav-warehouse" : undefined}
            isActive={isNavLinkActive(pathname, item.href)}
            onClick={(event: MouseEvent<HTMLAnchorElement>) => {
              event.preventDefault();
              router.push(item.href);
              if (narrow) {
                closeNav();
              }
            }}
          >
            {item.label}
          </SideNavMenuItem>
        ))}
      </SideNavMenu>
    );
  }

  function renderNavLink(href: string, label: string, className?: string, active = isNavLinkActive(pathname, href), Icon = navIcon(href)) {
    return (
      <SideNavLink
        key={href}
        href={href}
        renderIcon={Icon}
        className={className}
        isActive={active}
        onClick={(event) => {
          event.preventDefault();
          router.push(href);
          if (narrow || isAdministration) {
            closeNav();
          }
        }}
      >
        {label}
      </SideNavLink>
    );
  }

  async function handleLogout() {
    await logout();
    router.push("/clerk-login");
  }

  return (
    <div
      className="firstout-shell"
      data-nav-expanded={expanded ? "true" : "false"}
      data-compact={narrow ? "true" : "false"}
    >
      <Theme theme="g100">
        <Header aria-label="Firstout" className={loading ? "firstout-loading-motion" : undefined}>
          <SkipToContent />
          {/* isCollapsible keeps the hamburger visible at lg+ (Carbon otherwise hides it). */}
          <HeaderMenuButton
            aria-label={expanded ? "Collapse navigation" : "Expand navigation"}
            isActive={expanded}
            isCollapsible
            disabled={loading}
            onClick={toggleNav}
          />
          <HeaderName
            href="/"
            prefix=""
            className="firstout-brand"
            onClick={(event) => {
              event.preventDefault();
              router.push("/");
            }}
          >
            <img src="/brand/mark-on-dark.png" alt="Firstout" width={32} height={32} />
          </HeaderName>
          <div className="firstout-header-organisation">
            {loading
              ? <SkeletonPlaceholder className={loadingStyles.headerOrganisation} aria-hidden="true" />
              : <StaffOrganizationSwitcher />}
          </div>
          <HeaderGlobalBar>
            {loading ? (
              <>
                <div className="firstout-header-search" aria-hidden="true">
                  <SkeletonPlaceholder className={loadingStyles.headerSearch} />
                </div>
                <div className="firstout-header-user" aria-hidden="true">
                  <SkeletonText className={loadingStyles.headerUser} width="5rem" />
                </div>
                <div className={loadingStyles.headerAction} aria-hidden="true"><SkeletonPlaceholder /></div>
              </>
            ) : (
              <>
                <HeaderSearch
                  key={user ? user.team.id + ":" + user.id : undefined}
                  administrationUser={isAdministration ? user : undefined}
                />
                <span className="firstout-header-user" title={user?.email}>
                  {user?.display_name || user?.email}
                </span>
                <HeaderGlobalAction
                  aria-label="Log out"
                  tooltipAlignment="end"
                  onClick={() => void handleLogout()}
                >
                  <Logout size={20} />
                </HeaderGlobalAction>
              </>
            )}
          </HeaderGlobalBar>
        </Header>
        <SideNav
          aria-label="Firstout sections"
          aria-hidden={loading || undefined}
          className={loading ? "firstout-side-nav firstout-loading-motion" : "firstout-side-nav"}
          expanded={expanded && !(narrow && loading)}
          isRail={!narrow}
          isPersistent={!narrow}
          onOverlayClick={closeNav}
        >
          {loading ? (
            <div className={loadingStyles.navigation} aria-hidden="true">
              {Array.from({ length: 8 }, (_, index) => (
                <div className={loadingStyles.navItem} key={index}>
                  <SkeletonPlaceholder />
                  {expanded && <SkeletonText width="5rem" />}
                </div>
              ))}
            </div>
          ) : <SideNavItems>
            {renderNavLink(HOME_NAV_ITEM.href, HOME_NAV_ITEM.label)}
            {renderNavMenu(
              "Catalogue",
              Catalog,
              isCatalogueMenuPath(pathname),
              CATALOGUE_NAV_ITEMS,
              "catalogue",
            )}
            {renderNavMenu("Stock", Product, isStockPath(pathname), STOCK_NAV_ITEMS, "stock")}
            {renderNavMenu(
              "Warehouse",
              InventoryManagement,
              isWarehousePath(pathname),
              WAREHOUSE_NAV_ITEMS,
              "warehouse",
            )}
            {renderNavLink(TILL_NAV_ITEM.href, TILL_NAV_ITEM.label)}
            {salesNavItems.length ? renderNavMenu("Sales", Store, isSalesPath(pathname), salesNavItems, "sales") : null}
            {renderNavMenu("Books", Finance, isBooksPath(pathname), booksNavItems, "books")}
            {renderNavLink(administrationHome(user), "Admin", undefined, isAdministration, Settings)}
          </SideNavItems>}
        </SideNav>
      </Theme>
      <Theme theme="g10">
        {isAdministration ? (
          <div className={adminStyles.layout}>
            <Suspense>
              <AdminNavigation />
            </Suspense>
            <main id="main-content" className={`firstout-main ${adminStyles.main}`}>
              <div className={adminStyles.content}>
                <Suspense>
                  <AdminBreadcrumb />
                  <AdminNavigation mobile />
                </Suspense>
                {children}
              </div>
            </main>
          </div>
        ) : (
          <main id="main-content" className="firstout-main">
            <AppBreadcrumb />
            {loading ? <PageLoading kind="status" label="Loading your workspace…" /> : children}
          </main>
        )}
      </Theme>
    </div>
  );
}
