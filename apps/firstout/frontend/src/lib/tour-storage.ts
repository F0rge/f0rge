/** Per-user tour completion in this browser. v1 so a redesigned tour can show once. */
export const TOUR_STORAGE_PREFIX = "firstout-tour-v1:";

export type TourCompletion = "completed" | "skipped";

export type TourStore = {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
};

function browserStores(): TourStore[] {
  if (typeof window === "undefined") {
    return [];
  }
  const stores: TourStore[] = [];
  try {
    if (window.localStorage) {
      stores.push(window.localStorage);
    }
  } catch {
    // localStorage disabled.
  }
  try {
    if (window.sessionStorage) {
      stores.push(window.sessionStorage);
    }
  } catch {
    // sessionStorage disabled.
  }
  return stores;
}

function storesFor(store: TourStore | TourStore[] | null | undefined): TourStore[] {
  if (store === undefined) {
    return browserStores();
  }
  if (Array.isArray(store)) {
    return store;
  }
  return store ? [store] : [];
}

export function tourStorageKey(userId: string): string {
  return `${TOUR_STORAGE_PREFIX}${userId}`;
}

export function readTourCompletion(
  userId: string,
  store?: TourStore | TourStore[] | null,
): TourCompletion | null {
  if (!userId) {
    return null;
  }
  for (const resolved of storesFor(store)) {
    try {
      const value = resolved.getItem(tourStorageKey(userId));
      if (value === "completed" || value === "skipped") {
        return value;
      }
    } catch {
      // Try the next store. A quota or privacy error must not reopen the tour.
    }
  }
  return null;
}

export function writeTourCompletion(
  userId: string,
  completion: TourCompletion,
  store?: TourStore | TourStore[] | null,
): void {
  if (!userId) {
    return;
  }
  for (const resolved of storesFor(store)) {
    try {
      resolved.setItem(tourStorageKey(userId), completion);
    } catch {
      // Private mode and quota errors should still let the tour close.
    }
  }
}
