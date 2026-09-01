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
  Catalog,
  Delivery,
  DeliveryParcel,
  Document,
  Finance,
  Home,
  Industry,
  Location,
  Logout,
  Movement,
  Product,
  Purchase,
  Receipt,
  Settings,
  Store,
  User,
  UserMultiple,
  Wallet,
  ChartLine,
  DocumentTasks,
} from "@carbon/icons-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type MouseEvent, type ReactNode } from "react";

import { useAuth } from "@/lib/auth";
import { BOOKS_NAV_ITEMS, SIDE_NAV_ITEMS } from "@/lib/nav";

const ICONS = {
  "/": Home,
  "/locations": Location,
  "/suppliers": Industry,
  "/proformas": Document,
  "/catalogue": Catalog,
  "/stock": Product,
  "/purchase-orders": Purchase,
  "/transit": Delivery,
  "/receive": DeliveryParcel,
  "/transfers": Movement,
  "/ledger": Finance,
  "/contacts": UserMultiple,
  "/invoices": Receipt,
  "/bills": Purchase,
  "/payments": Wallet,
  "/bank-reconciliation": DocumentTasks,
  "/reports": ChartLine,
  "/vat201": Document,
  "/till": Store,
  "/users": UserMultiple,
  "/profile": User,
  "/settings": Settings,
} as const;

const BOOKS_HREFS = new Set<string>(BOOKS_NAV_ITEMS.map((item) => item.href));

function isBooksPath(pathname: string): boolean {
  return (
    BOOKS_HREFS.has(pathname) ||
    pathname.startsWith("/invoices/") ||
    pathname.startsWith("/bills/")
  );
}

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [expanded, setExpanded] = useState(true);
  const isLogin = pathname === "/login";

  useEffect(() => {
    if (!loading && !user && !isLogin) {
      router.replace("/login");
    }
  }, [loading, user, isLogin, router]);

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

  const navItems = SIDE_NAV_ITEMS.filter(
    (item) => !("ownerOnly" in item && item.ownerOnly) || user.role === "owner",
  );
  const tillIndex = navItems.findIndex((item) => item.href === "/till");
  const navBeforeBooks = tillIndex === -1 ? navItems : navItems.slice(0, tillIndex);
  const navAfterBooks = tillIndex === -1 ? [] : navItems.slice(tillIndex);

  function renderNavLink(item: (typeof navItems)[number]) {
    const Icon = ICONS[item.href];
    return (
      <SideNavLink
        key={item.href}
        href={item.href}
        renderIcon={Icon}
        isActive={pathname === item.href}
        onClick={(event) => {
          event.preventDefault();
          router.push(item.href);
        }}
      >
        {item.label}
      </SideNavLink>
    );
  }

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <div className="vellano-shell" data-nav-expanded={expanded ? "true" : "false"}>
      <Theme theme="g10">
        <Header aria-label="Vellano">
          <SkipToContent />
          <HeaderMenuButton
            aria-label={expanded ? "Close menu" : "Open menu"}
            isActive={expanded}
            onClick={() => setExpanded((current) => !current)}
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
        <SideNav aria-label="Vellano sections" expanded={expanded} isPersistent>
          <SideNavItems>
            {navBeforeBooks.map(renderNavLink)}
            <SideNavMenu
              key="books-menu"
              renderIcon={Finance}
              title="Books"
              defaultExpanded={isBooksPath(pathname)}
              isActive={isBooksPath(pathname)}
            >
              {BOOKS_NAV_ITEMS.map((booksItem) => {
                const BooksIcon = ICONS[booksItem.href];
                const active =
                  pathname === booksItem.href ||
                  (booksItem.href === "/invoices" && pathname.startsWith("/invoices/")) ||
                  (booksItem.href === "/bills" && pathname.startsWith("/bills/"));
                return (
                  <SideNavMenuItem
                    key={booksItem.href}
                    href={booksItem.href}
                    renderIcon={BooksIcon}
                    isActive={active}
                    onClick={(event: MouseEvent<HTMLAnchorElement>) => {
                      event.preventDefault();
                      router.push(booksItem.href);
                    }}
                  >
                    {booksItem.label}
                  </SideNavMenuItem>
                );
              })}
            </SideNavMenu>
            {navAfterBooks.map(renderNavLink)}
          </SideNavItems>
        </SideNav>
        <main id="main-content" className="vellano-main">
          {children}
        </main>
      </Theme>
    </div>
  );
}
