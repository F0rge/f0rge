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

type SideNavListener = () => void;

const listeners = new Set<SideNavListener>();
let expandedValue = true;
let hydrated = false;

function emit(): void {
  for (const listener of listeners) {
    listener();
  }
}

export function subscribeSideNavExpanded(listener: SideNavListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getSideNavExpandedSnapshot(): boolean {
  if (!hydrated) {
    expandedValue = readSideNavExpanded(true);
    hydrated = true;
  }
  return expandedValue;
}

/** SSR / first paint — expanded to match historical layout. */
export function getSideNavExpandedServerSnapshot(): boolean {
  return true;
}

export function setSideNavExpanded(expanded: boolean): void {
  expandedValue = expanded;
  hydrated = true;
  writeSideNavExpanded(expanded);
  emit();
}

export function toggleSideNavExpanded(): void {
  setSideNavExpanded(!getSideNavExpandedSnapshot());
}
