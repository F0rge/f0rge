/** Per-user tour completion in this browser. v1 so a redesigned tour can show once. */
export const TOUR_STORAGE_PREFIX = "firstout-tour-v1:";

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

export function tourStorageKey(userId: string): string {
  return `${TOUR_STORAGE_PREFIX}${userId}`;
}

export function readTourCompletion(userId: string, store?: TourStore | null): TourCompletion | null {
  const resolved = store === undefined ? browserStore() : store;
  if (!resolved || !userId) {
    return null;
  }
  try {
    const value = resolved.getItem(tourStorageKey(userId));
    if (value === "completed" || value === "skipped") {
      return value;
    }
    return null;
  } catch {
    return null;
  }
}

export function writeTourCompletion(
  userId: string,
  completion: TourCompletion,
  store?: TourStore | null,
): void {
  const resolved = store === undefined ? browserStore() : store;
  if (!resolved || !userId) {
    return;
  }
  try {
    resolved.setItem(tourStorageKey(userId), completion);
  } catch {
    // Private mode and quota errors should still let the tour close.
  }
}
