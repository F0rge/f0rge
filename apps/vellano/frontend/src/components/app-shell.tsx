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
  DocumentSubtract,
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
  ACCOUNT_NAV_ITEMS,
  BOOKS_NAV_ITEMS,
  NIA_NAV_ITEMS,
  OPERATIONS_NAV_ITEMS,
  PRIMARY_NAV_ITEMS,
  SALES_NAV_ITEMS,
  STOCK_NAV_ITEMS,
  isBooksPath,
  isNavLinkActive,
  isStockPath,
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
  "/proformas": Document,
  "/catalogue": Catalog,
  "/stock": Product,
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
  "/laybys": PiggyBank,
  "/customers": UserFollow,
  "/ledger": Finance,
  "/journals": Notebook,
  "/contacts": UserMultiple,
  "/invoices": Receipt,
  "/repeating-invoices": Renew,
  "/credit-notes": DocumentSubtract,
  "/bills": Purchase,
  "/payments": Wallet,
  "/bank-reconciliation": DocumentTasks,
  "/reports": ChartLine,
  "/canvas": ChartColumn,
  "/vat201": Document,
  "/till": Store,
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
  const isLogin = pathname === "/login";

  useEffect(() => {
    if (!loading && !user && !isLogin) {
      router.replace("/login");
    }
  }, [loading, user, isLogin, router]);

  useEffect(() => {
    if (user) {
      bindCanvasUser(user.id);
    }
  }, [user]);

  // Pathname tab changes must reset document/main scroll so the fixed header
  // does not clip page titles / primary actions from a prior scrolled page.
  // rAF: run after Next scroll restoration / layout paint.
  useEffect(() => {
    if (isLogin) {
      return;
    }
    resetMainScroll();
    const id = requestAnimationFrame(() => resetMainScroll());
    return () => cancelAnimationFrame(id);
  }, [pathname, isLogin]);

  if (isLogin) {
    return <>{children}</>;
  }

  if (loading) {
    return (
      <Theme theme="g10">
        <div className="vellano-shell-loading">
          <Loading withOverlay={false} description="Loading session…" />
        </div>
      </Theme>
    );
  }

  if (!user) {
    return null;
  }

  const accountItems = ACCOUNT_NAV_ITEMS.filter(
    (item) => !("permission" in item) || can(user, item.permission),
  );

  function renderNavLink(href: string, label: string) {
    const Icon = navIcon(href);
    return (
      <SideNavLink
        key={href}
        href={href}
        renderIcon={Icon}
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
      <div className="vellano-shell" data-nav-expanded={expanded ? "true" : "false"}>
        <Theme theme="g100">
          <Header aria-label="Vellano">
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
              Vellano
            </HeaderName>
            <HeaderGlobalBar>
              <HeaderSearch />
              {canUseNia(user) ? <NiaHeaderAction /> : null}
              <span className="vellano-header-user" title={user.email}>
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
          aria-label="Vellano sections"
          expanded={expanded}
          isRail
          isPersistent
          onOverlayClick={() => setSideNavExpanded(false)}
        >
          <SideNavItems>
            {PRIMARY_NAV_ITEMS.map((item) => renderNavLink(item.href, item.label))}
            <SideNavMenu
              key={isStockPath(pathname) ? "stock-open" : "stock-closed"}
              renderIcon={Product}
              title="Stock"
              defaultExpanded={isStockPath(pathname)}
              isActive={isStockPath(pathname)}
            >
              {STOCK_NAV_ITEMS.map((stockItem) => (
                <SideNavMenuItem
                  key={stockItem.href}
                  href={stockItem.href}
                  isActive={isNavLinkActive(pathname, stockItem.href)}
                  onClick={(event: MouseEvent<HTMLAnchorElement>) => {
                    event.preventDefault();
                    router.push(stockItem.href);
                  }}
                >
                  {stockItem.label}
                </SideNavMenuItem>
              ))}
            </SideNavMenu>
            {OPERATIONS_NAV_ITEMS.map((item) => renderNavLink(item.href, item.label))}
            {SALES_NAV_ITEMS.map((item) => renderNavLink(item.href, item.label))}
            <SideNavMenu
              key={isBooksPath(pathname) ? "books-open" : "books-closed"}
              renderIcon={Finance}
              title="Books"
              defaultExpanded={isBooksPath(pathname)}
              isActive={isBooksPath(pathname)}
            >
              {BOOKS_NAV_ITEMS.map((booksItem) => (
                <SideNavMenuItem
                  key={booksItem.href}
                  href={booksItem.href}
                  isActive={isNavLinkActive(pathname, booksItem.href)}
                  onClick={(event: MouseEvent<HTMLAnchorElement>) => {
                    event.preventDefault();
                    router.push(booksItem.href);
                  }}
                >
                  {booksItem.label}
                </SideNavMenuItem>
              ))}
            </SideNavMenu>
            {canUseNia(user)
              ? NIA_NAV_ITEMS.map((item) => renderNavLink(item.href, item.label))
              : null}
            {accountItems.map((item) => renderNavLink(item.href, item.label))}
          </SideNavItems>
        </SideNav>
      </Theme>
      <Theme theme="g10">
        <main id="main-content" className="vellano-main">
          {children}
        </main>
        {canUseNia(user) ? <NiaDockPanel enabled /> : null}
      </Theme>
    </div>
    </NiaDockProvider>
  );
}
