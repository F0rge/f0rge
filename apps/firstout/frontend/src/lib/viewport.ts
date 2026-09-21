/** Compact layout breakpoint (portrait phones). */
export const NARROW_VIEWPORT_MQ = "(max-width: 42rem)";

/**
 * WMS floor console + Warehouse nav: phones including landscape.
 * Width alone is not enough — coarse pointer + no hover catches landscape phones.
 */
export const WMS_MOBILE_VIEWPORT_MQ =
  "(max-width: 42rem), (hover: none) and (pointer: coarse)";

type ViewportListener = () => void;

function subscribeViewport(mq: string, listener: ViewportListener): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }
  const media = window.matchMedia(mq);
  media.addEventListener("change", listener);
  return () => media.removeEventListener("change", listener);
}

function getViewportSnapshot(mq: string): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.matchMedia(mq).matches;
}

export function subscribeNarrowViewport(listener: ViewportListener): () => void {
  return subscribeViewport(NARROW_VIEWPORT_MQ, listener);
}

export function getNarrowViewportSnapshot(): boolean {
  return getViewportSnapshot(NARROW_VIEWPORT_MQ);
}

export function subscribeWmsMobileViewport(listener: ViewportListener): () => void {
  return subscribeViewport(WMS_MOBILE_VIEWPORT_MQ, listener);
}

export function getWmsMobileViewportSnapshot(): boolean {
  return getViewportSnapshot(WMS_MOBILE_VIEWPORT_MQ);
}

/** SSR / first paint — assume desktop so Warehouse nav stays hidden until hydrate. */
export function getNarrowViewportServerSnapshot(): boolean {
  return false;
}

/** SSR / first paint — assume desktop interstitial until hydrate. */
export function getWmsMobileViewportServerSnapshot(): boolean {
  return false;
}
