"use client";

import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import { isProductAttentionEligible, productAttentionVisibility, ProductAttentionAccumulator } from "@/lib/analytics/attention";
import { useStorefrontAnalytics } from "./analytics-provider";

const activityEvents = ["pointerdown", "pointermove", "keydown", "scroll", "touchstart"] as const;

export function useProductAttention(productId: string): RefObject<HTMLDivElement | null> {
  const targetRef = useRef<HTMLDivElement>(null);
  const summarySentRef = useRef(false);
  const { choice, capture } = useStorefrontAnalytics();

  useEffect(() => {
    summarySentRef.current = false;
    const target = targetRef.current;
    if (!target || choice !== "accepted" || typeof IntersectionObserver === "undefined") return;

    const attention = new ProductAttentionAccumulator(() => performance.now());
    let visibility = 0;
    const measureFromEntry = (entry?: IntersectionObserverEntry) => {
      visibility = productAttentionVisibility(
        entry?.intersectionRatio ?? 0,
        entry?.intersectionRect.height ?? 0,
        entry?.rootBounds?.height || window.innerHeight,
      );
      attention.setEligible(isProductAttentionEligible(visibility, document.visibilityState, document.hasFocus()));
    };
    const updateEligibility = () => {
      attention.setEligible(isProductAttentionEligible(visibility, document.visibilityState, document.hasFocus()));
    };
    const observer = new IntersectionObserver(([entry]) => measureFromEntry(entry), { threshold: [0, 0.25, 0.5, 0.75, 1] });
    const onActivity = () => attention.noteInteraction();
    const onPageHide = (event: PageTransitionEvent) => {
      if (event.persisted) attention.setEligible(false);
      else sendSummary();
    };
    const sendSummary = () => {
      if (summarySentRef.current) return;
      const activeSeconds = attention.finish();
      if (activeSeconds === null) return;
      summarySentRef.current = true;
      capture({ name: "storefront_product_attention_summary", properties: { product_id: productId, active_seconds: activeSeconds, visibility_threshold: "half_visible" } });
    };

    observer.observe(target);
    for (const event of activityEvents) document.addEventListener(event, onActivity, { capture: true, passive: true });
    document.addEventListener("visibilitychange", updateEligibility);
    window.addEventListener("focus", updateEligibility);
    window.addEventListener("blur", updateEligibility);
    window.addEventListener("pageshow", updateEligibility);
    window.addEventListener("pagehide", onPageHide);
    const timer = window.setInterval(() => attention.sample(), 1000);

    return () => {
      window.clearInterval(timer);
      observer.disconnect();
      for (const event of activityEvents) document.removeEventListener(event, onActivity, true);
      document.removeEventListener("visibilitychange", updateEligibility);
      window.removeEventListener("focus", updateEligibility);
      window.removeEventListener("blur", updateEligibility);
      window.removeEventListener("pageshow", updateEligibility);
      window.removeEventListener("pagehide", onPageHide);
      sendSummary();
    };
  }, [capture, choice, productId]);

  return targetRef;
}
