/** Match the WMS / warehouse nav floor breakpoint (phone + tablet, including landscape). */
export const NARROW_VIEWPORT_MQ = "(max-width: 64rem), (pointer: coarse)";

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
