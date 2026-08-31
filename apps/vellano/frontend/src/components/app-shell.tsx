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
  SkipToContent,
  Theme,
} from "@carbon/react";
import {
  Finance,
  Home,
  Logout,
  Product,
  Purchase,
  Settings,
  Store,
  User,
  UserMultiple,
} from "@carbon/icons-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { useAuth } from "@/lib/auth";
import { SIDE_NAV_ITEMS } from "@/lib/nav";

const ICONS = {
  "/": Home,
  "/stock": Product,
  "/purchase-orders": Purchase,
  "/ledger": Finance,
  "/till": Store,
  "/users": UserMultiple,
  "/profile": User,
  "/settings": Settings,
} as const;

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
            {navItems.map((item) => {
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
            })}
          </SideNavItems>
        </SideNav>
        <main id="main-content" className="vellano-main">
          {children}
        </main>
      </Theme>
    </div>
  );
}
