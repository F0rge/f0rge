/** Camera entry points are for touch phones/tablets; keyboard barcode input stays universal. */
export interface MobileScanCapabilities {
  coarsePointer: boolean;
  touchPoints: number;
  userAgent: string;
  platform: string;
  mobile?: boolean;
}

export function supportsMobileScan(
  capabilities: MobileScanCapabilities,
): boolean {
  const mobileDevice =
    capabilities.mobile === true ||
    /Android|iPhone|iPad|iPod|Mobile|Silk/i.test(capabilities.userAgent) ||
    (capabilities.platform === "MacIntel" && capabilities.touchPoints > 1);
  return (
    mobileDevice && capabilities.coarsePointer && capabilities.touchPoints > 0
  );
}

/** A stable server snapshot avoids reading browser capabilities during prerender/hydration. */
export function getMobileScanServerSnapshot(): boolean {
  return false;
}

export function getMobileScanSnapshot(): boolean {
  if (typeof window === "undefined" || typeof navigator === "undefined")
    return false;
  const client = navigator as Navigator & {
    userAgentData?: { mobile?: boolean };
  };
  return supportsMobileScan({
    coarsePointer: window.matchMedia("(pointer: coarse)").matches,
    touchPoints: client.maxTouchPoints,
    userAgent: client.userAgent,
    platform: client.platform,
    mobile: client.userAgentData?.mobile,
  });
}

export function subscribeMobileScan(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const pointer = window.matchMedia("(pointer: coarse)");
  pointer.addEventListener("change", listener);
  window.addEventListener("resize", listener);
  return () => {
    pointer.removeEventListener("change", listener);
    window.removeEventListener("resize", listener);
  };
}
