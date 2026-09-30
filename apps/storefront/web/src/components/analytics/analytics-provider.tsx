"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { AnalyticsConsentPanel } from "./analytics-consent";
import { loadAnalyticsConsent, saveAnalyticsConsent, type AnalyticsConsentChoice, type ConsentStorage } from "@/lib/analytics/consent";
import { acquisitionProperties, analyticsPageForPathname, type BrowserAnalyticsProvider, type StorefrontBrowserEvent } from "@/lib/analytics/events";
import { configuredPostHogBrowserProvider } from "@/lib/analytics/posthog-browser";

type AnalyticsContextValue = {
  choice: AnalyticsConsentChoice | null;
  ready: boolean;
  capture(event: StorefrontBrowserEvent): void;
  choose(choice: AnalyticsConsentChoice): void;
  resetIdentity(): void;
};

const AnalyticsContext = createContext<AnalyticsContextValue | null>(null);

function browserConsentStorage(): ConsentStorage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

function PageViewTracker({ enabled, capture }: { enabled: boolean; capture(event: StorefrontBrowserEvent): void }) {
  const pathname = usePathname();
  const lastPageRef = useRef("");
  const attributionSentRef = useRef(false);

  useEffect(() => {
    if (!enabled || !pathname) return;
    const page = analyticsPageForPathname(pathname);
    if (!page) return;
    const pageKey = `${page.pageKey}:${page.productId || ""}`;
    if (lastPageRef.current === pageKey) return;

    const acquisition = attributionSentRef.current
      ? {}
      : acquisitionProperties(window.location.search, document.referrer);
    capture({
      name: "storefront_page_viewed",
      properties: { page_key: page.pageKey, ...(page.productId ? { product_id: page.productId } : {}), ...acquisition },
    });
    lastPageRef.current = pageKey;
    attributionSentRef.current = true;
  }, [capture, enabled, pathname]);

  return null;
}

export function useStorefrontAnalytics(): AnalyticsContextValue {
  const value = useContext(AnalyticsContext);
  if (!value) throw new Error("useStorefrontAnalytics must be used within StorefrontAnalyticsProvider");
  return value;
}

export function StorefrontAnalyticsProvider({ children }: { children: ReactNode }) {
  const [choice, setChoice] = useState<AnalyticsConsentChoice | null>(null);
  const [ready, setReady] = useState(false);
  const choiceRef = useRef<AnalyticsConsentChoice | null>(null);
  const providerRef = useRef<BrowserAnalyticsProvider & { resetIdentity(): void; revoke(): void } | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const saved = loadAnalyticsConsent(browserConsentStorage());
      choiceRef.current = saved;
      if (saved === "accepted") providerRef.current = configuredPostHogBrowserProvider();
      setChoice(saved);
      setReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const choose = useCallback((next: AnalyticsConsentChoice) => {
    saveAnalyticsConsent(browserConsentStorage(), next);
    choiceRef.current = next;
    if (next === "accepted") {
      if (!providerRef.current) providerRef.current = configuredPostHogBrowserProvider();
    } else {
      providerRef.current?.revoke();
      providerRef.current = null;
    }
    setChoice(next);
  }, []);

  const capture = useCallback((event: StorefrontBrowserEvent) => {
    if (choiceRef.current !== "accepted") return;
    try {
      providerRef.current?.capture(event);
    } catch { /* Analytics failures never interrupt shopping. */ }
  }, []);

  const resetIdentity = useCallback(() => {
    try { providerRef.current?.resetIdentity(); } catch { /* Analytics failures never interrupt account actions. */ }
  }, []);

  const value = useMemo(() => ({ choice, ready, capture, choose, resetIdentity }), [capture, choice, choose, ready, resetIdentity]);
  return <AnalyticsContext.Provider value={value}>
    {children}
    <PageViewTracker enabled={choice === "accepted"} capture={capture} />
    <AnalyticsConsentPanel choice={choice} ready={ready} choose={choose} />
  </AnalyticsContext.Provider>;
}
