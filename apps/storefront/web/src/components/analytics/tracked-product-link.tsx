"use client";

import Link from "next/link";
import { useEffect, useRef, type ComponentProps } from "react";
import { analyticsSurfaceForPathname, type AnalyticsSurface } from "@/lib/analytics/events";
import { useStorefrontAnalytics } from "./analytics-provider";

function currentSurface(): AnalyticsSurface | null {
  return typeof window === "undefined" ? null : analyticsSurfaceForPathname(window.location.pathname);
}

// A card with several links to one piece sends its impression from one of them (impression={false} on the others).
export function TrackedProductLink({ href, productId, impression = true, children, ...link }: Omit<ComponentProps<typeof Link>, "href" | "onClick" | "ref"> & {
  href: string;
  productId: string;
  impression?: boolean;
}) {
  const linkRef = useRef<HTMLAnchorElement>(null);
  const impressionSentRef = useRef(false);
  const { choice, capture } = useStorefrontAnalytics();

  useEffect(() => {
    const element = linkRef.current;
    if (!element || !impression || choice !== "accepted" || impressionSentRef.current || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry || entry.intersectionRatio < 0.5 || impressionSentRef.current) return;
      const surface = currentSurface();
      if (!surface) return;
      impressionSentRef.current = true;
      capture({ name: "storefront_product_impressed", properties: { product_id: productId, surface } });
      observer.disconnect();
    }, { threshold: [0.5] });
    observer.observe(element.closest("[data-product-card]") ?? element);
    return () => observer.disconnect();
  }, [capture, choice, impression, productId]);

  return <Link {...link} ref={linkRef} href={href} onClick={() => {
    const surface = currentSurface();
    if (surface) capture({ name: "storefront_product_selected", properties: { product_id: productId, surface } });
  }}>
    {children}
  </Link>;
}
