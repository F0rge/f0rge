"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { AnalyticsConsentPanel } from "./analytics-consent";
import { loadAnalyticsConsent, saveAnalyticsConsent, type AnalyticsConsentChoice, type ConsentStorage } from "@/lib/analytics/consent";
import { ANALYTICS_CUSTOMER_TYPE_HEADER, ANALYTICS_ID_HEADER } from "@/lib/analytics/attribution";
import { acquisitionProperties, analyticsPageForPathname, type StorefrontBrowserEvent } from "@/lib/analytics/events";
import { configuredPostHogBrowserProvider, type PostHogBrowserProvider } from "@/lib/analytics/posthog-browser";
import { decideReplay, type ReplayVendorConfig } from "@/lib/analytics/replay";
import { subscribeToStudyEvents } from "@/app/study/study-events";

type AnalyticsContextValue = {
  choice: AnalyticsConsentChoice | null;
  ready: boolean;
  capture(event: StorefrontBrowserEvent): void;
  choose(choice: AnalyticsConsentChoice): void;
  resetIdentity(): void;
  identify(customerId: string, options?: { created?: boolean }): void;
  attributionHeaders(): Record<string, string>;
  setSensitiveOverlay(active: boolean): void;
};

const AnalyticsContext = createContext<AnalyticsContextValue | null>(null);
let lastTrackedPageKey = "";
let attributionSent = false;

function browserConsentStorage(): ConsentStorage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

function PageViewTracker({ enabled, capture }: { enabled: boolean; capture(event: StorefrontBrowserEvent): void }) {
  const pathname = usePathname();

  useEffect(() => {
    if (!enabled) {
      lastTrackedPageKey = "";
      attributionSent = false;
      return;
    }
    if (!pathname) return;
    const page = analyticsPageForPathname(pathname);
    if (!page) return;
    const pageKey = `${page.pageKey}:${page.productId || ""}`;
    if (lastTrackedPageKey === pageKey) return;

    const acquisition = attributionSent ? {} : acquisitionProperties(window.location.search, document.referrer);
    capture({
      name: "storefront_page_viewed",
      properties: { page_key: page.pageKey, ...(page.productId ? { product_id: page.productId } : {}), ...acquisition },
    });
    lastTrackedPageKey = pageKey;
    attributionSent = true;
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
  const providerRef = useRef<PostHogBrowserProvider | null>(null);
  const replayConfigRef = useRef<ReplayVendorConfig | null>(null);
  const [overlay, setOverlay] = useState(false);
  const [attributionVersion, setAttributionVersion] = useState(0);
  const pathname = usePathname() || "/";

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const saved = loadAnalyticsConsent(browserConsentStorage());
      choiceRef.current = saved;
      if (saved === "accepted") providerRef.current = configuredPostHogBrowserProvider();
      setChoice(saved);
      setAttributionVersion((version) => version + 1);
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
      replayConfigRef.current = null;
    }
    setChoice(next);
    setAttributionVersion((version) => version + 1);
  }, []);

  const capture = useCallback((event: StorefrontBrowserEvent) => {
    if (choiceRef.current !== "accepted") return;
    try {
      providerRef.current?.capture(event);
    } catch { /* Analytics failures never interrupt shopping. */ }
  }, []);

  const resetIdentity = useCallback(() => {
    try { providerRef.current?.resetIdentity(); } catch { /* Analytics failures never interrupt account actions. */ }
    setAttributionVersion((version) => version + 1);
  }, []);

  const identify = useCallback((customerId: string, options?: { created?: boolean }) => {
    if (choiceRef.current !== "accepted") return;
    try { providerRef.current?.identify(customerId, options); } catch { /* Analytics failures never interrupt sign-in. */ }
    setAttributionVersion((version) => version + 1);
  }, []);

  const attributionHeaders = useCallback((): Record<string, string> => {
    if (choiceRef.current !== "accepted") return {};
    const id = providerRef.current?.distinctId();
    if (!id) return {};
    return {
      [ANALYTICS_ID_HEADER]: id,
      [ANALYTICS_CUSTOMER_TYPE_HEADER]: providerRef.current?.customerType() || "guest",
    };
  }, []);

  const setSensitiveOverlay = useCallback((active: boolean) => {
    setOverlay(active);
  }, []);

  useEffect(() => {
    return subscribeToStudyEvents((detail) => {
      if (detail.type === "entry") capture({ name: "storefront_study_entered", properties: { study_id: detail.studyId } });
      if (detail.type === "progress") capture({ name: "storefront_study_progress", properties: { study_id: detail.studyId, milestone: detail.milestone } });
      if (detail.type === "finish") capture({ name: "storefront_study_finished", properties: { study_id: detail.studyId } });
    });
  }, [capture]);

  useEffect(() => {
    const decision = decideReplay({
      consent: choice,
      sessionKey: providerRef.current?.distinctId() ?? null,
      pathname,
      sensitiveOverlay: overlay,
    });
    replayConfigRef.current = decision.record ? decision.config : null;
  }, [attributionVersion, choice, overlay, pathname]);

  const value = useMemo(() => ({ choice, ready, capture, choose, resetIdentity, identify, attributionHeaders, setSensitiveOverlay }), [attributionHeaders, capture, choice, choose, identify, ready, resetIdentity, setSensitiveOverlay]);
  return <AnalyticsContext.Provider value={value}>
    {children}
    <PageViewTracker enabled={choice === "accepted"} capture={capture} />
    <AnalyticsConsentPanel choice={choice} ready={ready} choose={choose} />
  </AnalyticsContext.Provider>;
}
