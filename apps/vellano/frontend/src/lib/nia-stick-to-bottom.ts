/** Near-bottom threshold for Nia chat stick-to-bottom (px). */
export const NIA_NEAR_BOTTOM_PX = 100;

export type ScrollMetrics = {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
};

/** True when the scroller is within `thresholdPx` of the bottom. */
export function isNearBottom(
  metrics: ScrollMetrics,
  thresholdPx: number = NIA_NEAR_BOTTOM_PX,
): boolean {
  const distance = metrics.scrollHeight - metrics.scrollTop - metrics.clientHeight;
  return distance <= thresholdPx;
}

/** Instantly pin a messages scroller to the bottom. */
export function scrollElementToBottom(el: HTMLElement): void {
  el.scrollTop = el.scrollHeight;
}

export function readScrollMetrics(el: HTMLElement): ScrollMetrics {
  return {
    scrollTop: el.scrollTop,
    scrollHeight: el.scrollHeight,
    clientHeight: el.clientHeight,
  };
}
