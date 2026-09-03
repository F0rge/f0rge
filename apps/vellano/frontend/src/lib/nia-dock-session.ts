export const OPEN_STORAGE_KEY = "vellano-nia-dock-open";
export const THREAD_STORAGE_KEY = "vellano-nia-dock-thread";

function persistableStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.sessionStorage;
}

export function readDockOpen(): boolean {
  const store = persistableStorage();
  if (!store) {
    return false;
  }
  const raw = store.getItem(OPEN_STORAGE_KEY);
  return raw === "1" || raw === "true";
}

export function writeDockOpen(open: boolean): void {
  const store = persistableStorage();
  if (!store) {
    return;
  }
  store.setItem(OPEN_STORAGE_KEY, open ? "1" : "0");
}

export function readDockThreadId(): string | null {
  const store = persistableStorage();
  if (!store) {
    return null;
  }
  const raw = store.getItem(THREAD_STORAGE_KEY);
  return raw ? raw : null;
}

export function writeDockThreadId(id: string | null): void {
  const store = persistableStorage();
  if (!store) {
    return;
  }
  if (id === null) {
    store.removeItem(THREAD_STORAGE_KEY);
    return;
  }
  store.setItem(THREAD_STORAGE_KEY, id);
}

export function clearDockSession(): void {
  const store = persistableStorage();
  if (!store) {
    return;
  }
  store.removeItem(OPEN_STORAGE_KEY);
  store.removeItem(THREAD_STORAGE_KEY);
}
