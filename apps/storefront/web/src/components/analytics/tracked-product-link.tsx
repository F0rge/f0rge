"use client";

import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";
import { analyticsSurfaceForPathname, type AnalyticsSurface } from "@/lib/analytics/events";
import { useStorefrontAnalytics } from "./analytics-provider";

function currentSurface(): AnalyticsSurface | null {
  return typeof window === "undefined" ? null : analyticsSurfaceForPathname(window.location.pathname);
}

export function TrackedProductLink({ href, productId, className, children }: {
  href: string;
  productId: string;
  className: string;
  children: ReactNode;
}) {
  const linkRef = useRef<HTMLAnchorElement>(null);
  const impressionSentRef = useRef(false);
  const { choice, capture } = useStorefrontAnalytics();

  useEffect(() => {
    const element = linkRef.current;
    if (!element || choice !== "accepted" || impressionSentRef.current || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry || entry.intersectionRatio < 0.5 || impressionSentRef.current) return;
      const surface = currentSurface();
      if (!surface) return;
      impressionSentRef.current = true;
      capture({ name: "storefront_product_impressed", properties: { product_id: productId, surface } });
      observer.disconnect();
    }, { threshold: [0.5] });
    observer.observe(element);
    return () => observer.disconnect();
  }, [capture, choice, productId]);

  return <Link ref={linkRef} href={href} className={className} onClick={() => {
    const surface = currentSurface();
    if (surface) capture({ name: "storefront_product_selected", properties: { product_id: productId, surface } });
  }}>
    {children}
  </Link>;
}
