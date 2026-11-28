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
  Catalog,
  ChartLine,
  DeliveryTruck,
  Finance,
  Home,
  InventoryManagement,
  Logout,
  Money,
  Settings,
  ShoppingCart,
  Tag,
} from "@carbon/icons-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, useSyncExternalStore, type MouseEvent, type ReactNode } from "react";

import { StaffOrganizationSwitcher, useStaffSession } from "@/components/staff-provider";
import { isPublicAuthPath, missingSessionDestination } from "@/lib/auth-routes";
import { useAuth } from "@/lib/auth";
import { resetMainScroll } from "@/lib/reset-main-scroll";
import { isNavLinkActive, navGroupForPath, navGroupsFor, type NavGroupId } from "@/lib/nav";
import { AppBreadcrumb } from "@/components/app-breadcrumb";
import { AdminBreadcrumb, AdminNavigation } from "@/components/administration";
import adminStyles from "@/components/administration.module.css";
import { administrationHome, isAdminPath } from "@/lib/admin-navigation";
import navStyles from "@/components/workspace-nav.module.css";
import { WorkspaceLoader } from "@/components/workspace-loader";
import loadingStyles from "@/components/auth-loading.module.css";
import { HeaderSearch } from "@/components/header-search";
import { SkuPanelProvider } from "@/components/sku-panel/provider";
import { SkuPanel } from "@/components/sku-panel/sku-panel";
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

const GROUP_ICONS = {
  home: Home,
  till: Money,
  sell: Tag,
  products: Catalog,
  buy: ShoppingCart,
  warehouse: DeliveryTruck,
  stock: InventoryManagement,
  books: Finance,
  reports: ChartLine,
} satisfies Record<NavGroupId, typeof Home>;

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

  async function handleLogout() {
    await logout();
    router.push("/clerk-login");
  }

  return (
    <SkuPanelProvider>
    <div
      className="firstout-shell"
      data-nav-expanded={expanded ? "true" : "false"}
      data-compact={narrow ? "true" : "false"}
      // The Administration layout adds its own nav column, so the SKU panel's inset rules treat it like an open nav.
      data-administration={isAdministration ? "true" : undefined}
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
          ) : (
            <Suspense>
              <WorkspaceNavItems
                pathname={pathname}
                adminHref={administrationHome(user)}
                isAdministration={isAdministration}
                onNavigate={(href) => {
                  router.push(href);
                  if (narrow || isAdministration) closeNav();
                }}
              />
            </Suspense>
          )}
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
            <Suspense>
              <AppBreadcrumb />
            </Suspense>
            {loading ? <WorkspaceLoader /> : children}
          </main>
        )}
        {!loading && (
          <Suspense>
            <SkuPanel />
          </Suspense>
        )}
      </Theme>
    </div>
    </SkuPanelProvider>
  );
}

/** The workspace sidebar: groups this person can use, the current page's group open on load. */
function WorkspaceNavItems({ pathname, adminHref, isAdministration, onNavigate }: {
  pathname: string;
  adminHref: string;
  isAdministration: boolean;
  onNavigate: (href: string) => void;
}) {
  const { user } = useAuth();
  const section = useSearchParams().get("section");
  const currentGroup = isAdministration ? undefined : navGroupForPath(pathname)?.id;
  const follow = (href: string) => (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onNavigate(href);
  };

  return (
    <SideNavItems>
      {navGroupsFor(user).map((group) => {
        const Icon = GROUP_ICONS[group.id];
        if (group.link) {
          const page = group.pages[0];
          const active = isNavLinkActive(pathname, page.href);
          return (
            <SideNavLink key={group.id} href={page.href} renderIcon={Icon} isActive={active} aria-current={active ? "page" : undefined} onClick={follow(page.href)}>
              {group.label}
            </SideNavLink>
          );
        }
        const open = currentGroup === group.id;
        return (
          <SideNavMenu
            // A new key when the current group changes re-applies defaultExpanded after navigation.
            key={open ? `${group.id}-open` : `${group.id}-closed`}
            renderIcon={Icon}
            title={group.label}
            defaultExpanded={open}
            isActive={open}
          >
            {group.pages.map((page) => {
              const active = isNavLinkActive(pathname, page.href, section);
              return (
              <SideNavMenuItem
                key={page.href}
                href={page.href}
                className={page.mobileOnly ? "firstout-nav-warehouse" : undefined}
                isActive={active}
                aria-current={active ? "page" : undefined}
                onClick={follow(page.href)}
              >
                {page.access === "view" ? (
                  <span className={navStyles.item}>
                    {page.label}
                    <span className={navStyles.view} aria-hidden="true">view</span>
                    <span className="cds--visually-hidden">, view only</span>
                  </span>
                ) : page.label}
              </SideNavMenuItem>
              );
            })}
          </SideNavMenu>
        );
      })}
      <SideNavLink href={adminHref} renderIcon={Settings} isActive={isAdministration} aria-current={isAdministration ? "page" : undefined} onClick={follow(adminHref)}>
        Admin
      </SideNavLink>
    </SideNavItems>
  );
}
