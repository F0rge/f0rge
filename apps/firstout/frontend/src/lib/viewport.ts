/** Compact layout breakpoint (portrait phones). 42rem = 672px at 16px root. */
export const NARROW_VIEWPORT_MQ = "(max-width: 42rem)";
export const NARROW_VIEWPORT_PX = 672;

/**
 * WMS floor console + Warehouse nav: phones including landscape.
 * Width alone is not enough — coarse pointer + no hover catches landscape phones.
 */
export const WMS_MOBILE_VIEWPORT_MQ =
  "(max-width: 42rem), (hover: none) and (pointer: coarse)";

type ViewportListener = () => void;

function currentCssWidth(): number {
  if (typeof window === "undefined") {
    return NARROW_VIEWPORT_PX + 1;
  }
  const visual = window.visualViewport?.width;
  if (typeof visual === "number" && visual > 0) {
    return visual;
  }
  return window.innerWidth;
}

function matchesMedia(mq: string): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.matchMedia(mq).matches;
}

function subscribeViewport(mq: string, listener: ViewportListener): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }
  const media = window.matchMedia(mq);
  media.addEventListener("change", listener);
  window.addEventListener("resize", listener);
  window.visualViewport?.addEventListener("resize", listener);
  return () => {
    media.removeEventListener("change", listener);
    window.removeEventListener("resize", listener);
    window.visualViewport?.removeEventListener("resize", listener);
  };
}

function getViewportSnapshot(mq: string): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return matchesMedia(mq);
}

export function subscribeNarrowViewport(listener: ViewportListener): () => void {
  return subscribeViewport(NARROW_VIEWPORT_MQ, listener);
}

export function getNarrowViewportSnapshot(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return matchesMedia(NARROW_VIEWPORT_MQ) || currentCssWidth() <= NARROW_VIEWPORT_PX;
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
