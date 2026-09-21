"use client";

import {
  Header,
  HeaderGlobalAction,
  HeaderGlobalBar,
  HeaderMenuButton,
  HeaderName,
  Loading,
  SideNav,
  SideNavItems,
  SideNavLink,
  SideNavMenu,
  SideNavMenuItem,
  SkipToContent,
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
  ChartColumn,
  ChartLine,
  Currency,
  DocumentSubtract,
  Security,
  DocumentTasks,
} from "@carbon/icons-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore, type MouseEvent, type ReactNode } from "react";

import { useAuth } from "@/lib/auth";
import { bindCanvasUser } from "@/lib/nia-canvas-store";
import { clearDockSession } from "@/lib/nia-dock-session";
import { resetMainScroll } from "@/lib/reset-main-scroll";
import { can } from "@/lib/permissions";
import {
  ADMIN_NAV_ITEMS,
  BOOKS_NAV_ITEMS,
  CATALOGUE_NAV_ITEMS,
  HOME_NAV_ITEM,
  NIA_NAV_ITEMS,
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
import { HeaderSearch } from "@/components/header-search";
import {
  NiaDockPanel,
  NiaDockProvider,
  NiaHeaderAction,
} from "@/components/nia/nia-dock";
import { canUseNia } from "@/lib/permissions";
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
  "/canvas": ChartColumn,
  "/vat201": Document,
  "/books-periods": Calendar,
  "/till": Store,
  "/audit": Security,
  "/users": UserMultiple,
  "/roles": UserAdmin,
  "/profile": User,
  "/settings": Settings,
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
  const expanded = useSyncExternalStore(
    subscribeSideNavExpanded,
    getSideNavExpandedSnapshot,
    getSideNavExpandedServerSnapshot,
  );
  const isPublic =
    pathname === "/login" || pathname.startsWith("/trade") || pathname.startsWith("/c/");

  useEffect(() => {
    if (!loading && !user && !isPublic) {
      router.replace("/login");
    }
  }, [loading, user, isPublic, router]);

  useEffect(() => {
    if (user) {
      bindCanvasUser(user.id);
    }
  }, [user]);

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

  if (loading) {
    return (
      <Theme theme="g10">
        <div className="firstout-shell-loading">
          <Loading withOverlay={false} description="Loading session…" />
        </div>
      </Theme>
    );
  }

  if (!user) {
    return null;
  }

  const adminItems = ADMIN_NAV_ITEMS.filter(
    (item) => !("permission" in item) || can(user, item.permission),
  );

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
            }}
          >
            {item.label}
          </SideNavMenuItem>
        ))}
      </SideNavMenu>
    );
  }

  function renderNavLink(href: string, label: string, className?: string) {
    const Icon = navIcon(href);
    return (
      <SideNavLink
        key={href}
        href={href}
        renderIcon={Icon}
        className={className}
        isActive={isNavLinkActive(pathname, href)}
        onClick={(event) => {
          event.preventDefault();
          router.push(href);
        }}
      >
        {label}
      </SideNavLink>
    );
  }

  async function handleLogout() {
    clearDockSession();
    await logout();
    router.push("/login");
  }

  return (
    <NiaDockProvider enabled={canUseNia(user)}>
      <div className="firstout-shell" data-nav-expanded={expanded ? "true" : "false"}>
        <Theme theme="g100">
          <Header aria-label="Firstout">
            <SkipToContent />
            {/* isCollapsible keeps the hamburger visible at lg+ (Carbon otherwise hides it). */}
            <HeaderMenuButton
              aria-label={expanded ? "Collapse navigation" : "Expand navigation"}
              isActive={expanded}
              isCollapsible
              onClick={toggleSideNavExpanded}
            />
            <HeaderName
              href="/"
              prefix="F0rge"
              onClick={(event) => {
                event.preventDefault();
                router.push("/");
              }}
            >
              Firstout
            </HeaderName>
            <HeaderGlobalBar>
              <HeaderSearch />
              {canUseNia(user) ? <NiaHeaderAction /> : null}
              <span className="firstout-header-user" title={user.email}>
                {user.display_name || user.email}
              </span>
              <HeaderGlobalAction
                aria-label="Log out"
                tooltipAlignment="end"
                onClick={() => void handleLogout()}
              >
                <Logout size={20} />
              </HeaderGlobalAction>
            </HeaderGlobalBar>
          </Header>
        <SideNav
          aria-label="Firstout sections"
          expanded={expanded}
          isRail
          isPersistent
          onOverlayClick={() => setSideNavExpanded(false)}
        >
          <SideNavItems>
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
            {renderNavMenu("Sales", Store, isSalesPath(pathname), SALES_NAV_ITEMS, "sales")}
            {renderNavMenu("Books", Finance, isBooksPath(pathname), BOOKS_NAV_ITEMS, "books")}
            {canUseNia(user)
              ? NIA_NAV_ITEMS.map((item) => renderNavLink(item.href, item.label))
              : null}
            {renderNavMenu("Admin", Settings, isAdminPath(pathname), adminItems, "admin")}
          </SideNavItems>
        </SideNav>
      </Theme>
      <Theme theme="g10">
        <main id="main-content" className="firstout-main">
          {children}
        </main>
        {canUseNia(user) ? <NiaDockPanel enabled /> : null}
      </Theme>
    </div>
    </NiaDockProvider>
  );
}
