/** Per-user tour completion in this browser. v2 so the page/overview split shows once. */
export const TOUR_STORAGE_PREFIX = "firstout-tour-v2:";

export type TourCompletion = "completed" | "skipped";

export type TourStore = {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
};

function browserStore(): TourStore | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function pageTourStorageKey(userId: string, tourId: string): string {
  return `${TOUR_STORAGE_PREFIX}page:${userId}:${tourId}`;
}

export function overviewStorageKey(userId: string): string {
  return `${TOUR_STORAGE_PREFIX}overview:${userId}`;
}

function readCompletion(key: string, store?: TourStore | null): TourCompletion | null {
  const resolved = store === undefined ? browserStore() : store;
  if (!resolved) {
    return null;
  }
  try {
    const value = resolved.getItem(key);
    if (value === "completed" || value === "skipped") {
      return value;
    }
    return null;
  } catch {
    return null;
  }
}

function writeCompletion(key: string, completion: TourCompletion, store?: TourStore | null): void {
  const resolved = store === undefined ? browserStore() : store;
  if (!resolved) {
    return;
  }
  try {
    resolved.setItem(key, completion);
  } catch {
    // Private mode and quota errors should still let the tour close.
  }
}

export function readPageTourCompletion(
  userId: string,
  tourId: string,
  store?: TourStore | null,
): TourCompletion | null {
  if (!userId || !tourId) {
    return null;
  }
  return readCompletion(pageTourStorageKey(userId, tourId), store);
}

export function writePageTourCompletion(
  userId: string,
  tourId: string,
  completion: TourCompletion,
  store?: TourStore | null,
): void {
  if (!userId || !tourId) {
    return;
  }
  writeCompletion(pageTourStorageKey(userId, tourId), completion, store);
}

export function readOverviewCompletion(userId: string, store?: TourStore | null): TourCompletion | null {
  if (!userId) {
    return null;
  }
  return readCompletion(overviewStorageKey(userId), store);
}

export function writeOverviewCompletion(
  userId: string,
  completion: TourCompletion,
  store?: TourStore | null,
): void {
  if (!userId) {
    return;
  }
  writeCompletion(overviewStorageKey(userId), completion, store);
}
