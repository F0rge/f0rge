/** Persist SideNav expanded/collapsed across the browser session. */
export const SIDE_NAV_EXPANDED_KEY = "vellano-side-nav-expanded";

function persistableStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.sessionStorage;
}

/** Default expanded when unset — matches historical shell layout. */
export function readSideNavExpanded(defaultExpanded = true): boolean {
  const store = persistableStorage();
  if (!store) {
    return defaultExpanded;
  }
  const raw = store.getItem(SIDE_NAV_EXPANDED_KEY);
  if (raw === null) {
    return defaultExpanded;
  }
  return raw === "1" || raw === "true";
}

export function writeSideNavExpanded(expanded: boolean): void {
  const store = persistableStorage();
  if (!store) {
    return;
  }
  store.setItem(SIDE_NAV_EXPANDED_KEY, expanded ? "1" : "0");
}
