/** Match the WMS / warehouse nav narrow breakpoint (42rem). */
export const NARROW_VIEWPORT_MQ = "(max-width: 42rem)";

type ViewportListener = () => void;

export function subscribeNarrowViewport(listener: ViewportListener): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }
  const media = window.matchMedia(NARROW_VIEWPORT_MQ);
  media.addEventListener("change", listener);
  return () => media.removeEventListener("change", listener);
}

export function getNarrowViewportSnapshot(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.matchMedia(NARROW_VIEWPORT_MQ).matches;
}

/** SSR / first paint — assume desktop so Warehouse nav stays hidden until hydrate. */
export function getNarrowViewportServerSnapshot(): boolean {
  return false;
}
