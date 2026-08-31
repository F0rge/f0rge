"use client";

import {
  Content,
  Header,
  HeaderGlobalAction,
  HeaderGlobalBar,
  HeaderMenuButton,
  HeaderName,
  SideNav,
  SideNavItems,
  SideNavLink,
  SkipToContent,
  Theme,
} from "@carbon/react";
import {
  Finance,
  Home,
  Login,
  Product,
  Purchase,
  Settings,
  Store,
} from "@carbon/icons-react";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { SIDE_NAV_ITEMS } from "@/lib/nav";

const ICONS = {
  "/": Home,
  "/stock": Product,
  "/purchase-orders": Purchase,
  "/ledger": Finance,
  "/till": Store,
  "/settings": Settings,
} as const;

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [expanded, setExpanded] = useState(true);

  return (
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
          <HeaderGlobalAction
            aria-label="Log in"
            tooltipAlignment="end"
            onClick={() => router.push("/login")}
          >
            <Login size={20} />
          </HeaderGlobalAction>
        </HeaderGlobalBar>
        <SideNav aria-label="Vellano sections" expanded={expanded} isPersistent>
          <SideNavItems>
            {SIDE_NAV_ITEMS.map((item) => {
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
      </Header>
      <Content id="main-content">{children}</Content>
    </Theme>
  );
}
