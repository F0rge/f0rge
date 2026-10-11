"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { usePathname } from "next/navigation";

export function StorefrontMotion({ children }: { children: ReactNode }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  useEffect(() => {
    const root = rootRef.current;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!root || reducedMotion.matches || !("IntersectionObserver" in window) || !("animate" in Element.prototype)) return;

    const animations = new Map<HTMLElement, Animation>();
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        if (!(entry.target instanceof HTMLElement)) continue;
        const element = entry.target;
        observer.unobserve(element);
        if (reducedMotion.matches || element.matches(":focus-within")) continue;
        const animation = element.animate(
          [{ opacity: .94, transform: "translateY(10px)" }, { opacity: 1, transform: "translateY(0)" }],
          { duration: 400, easing: "cubic-bezier(0.2, 0.65, 0.3, 1)" },
        );
        animations.set(element, animation);
        animation.onfinish = () => animations.delete(element);
      }
    }, { threshold: .1 });
    root.querySelectorAll<HTMLElement>("[data-reveal]").forEach((element) => observer.observe(element));

    const cancelFocused = (event: FocusEvent) => {
      if (!(event.target instanceof Node)) return;
      for (const [element, animation] of animations) {
        if (element.contains(event.target)) {
          animation.cancel();
          animations.delete(element);
        }
      }
    };
    const stopMotion = () => {
      if (!reducedMotion.matches) return;
      observer.disconnect();
      animations.forEach((animation) => animation.cancel());
      animations.clear();
    };
    root.addEventListener("focusin", cancelFocused);
    reducedMotion.addEventListener("change", stopMotion);

    return () => {
      observer.disconnect();
      root.removeEventListener("focusin", cancelFocused);
      reducedMotion.removeEventListener("change", stopMotion);
      animations.forEach((animation) => animation.cancel());
    };
  }, [pathname]);

  return <div ref={rootRef}>{children}</div>;
}
