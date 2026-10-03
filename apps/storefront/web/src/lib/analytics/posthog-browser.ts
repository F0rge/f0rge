import { opaqueAnalyticsId, type AnalyticsCustomerType } from "./attribution";
import { sanitizeAnalyticsEvent, type AnalyticsProperties, type BrowserAnalyticsProvider, type StorefrontBrowserEvent } from "./events";
import { analyticsEnvironment } from "./policy";

export const POSTHOG_EU_HOST = "https://eu.i.posthog.com";
export const POSTHOG_CAPTURE_URL = `${POSTHOG_EU_HOST}/i/v0/e/`;

export type PostHogCapturePayload = {
  api_key: string;
  event: string;
  distinct_id: string;
  properties: Record<string, boolean | number | string>;
};

export type PostHogBrowserProvider = BrowserAnalyticsProvider & {
  readonly isConfigured: boolean;
  distinctId(): string | null;
  customerType(): AnalyticsCustomerType;
  resetIdentity(): void;
  identify(customerId: string, options?: { created?: boolean }): void;
  revoke(): void;
};

type ProviderOptions = {
  projectToken?: string;
  fetcher?: typeof fetch;
  createDistinctId?: () => string;
};

function createAnonymousId(): string {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi && typeof cryptoApi.randomUUID === "function") return cryptoApi.randomUUID();
  const bytes = new Uint8Array(16);
  if (cryptoApi?.getRandomValues) {
    cryptoApi.getRandomValues(bytes);
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  return `visitor-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

/** Minimal PostHog Cloud capture adapter: no SDK autocapture, cookies, or persistent identity. */
export function createPostHogBrowserProvider(options: ProviderOptions = {}): PostHogBrowserProvider {
  const token = options.projectToken?.trim() || "";
  const fetcher = options.fetcher || globalThis.fetch;
  const createDistinctId = options.createDistinctId || createAnonymousId;
  const pending = new Set<AbortController>();
  let distinctId = token ? createDistinctId() : null;
  let customerType: AnalyticsCustomerType = "guest";
  let enabled = Boolean(token);

  function send(name: string, properties: AnalyticsProperties, id: string): void {
    const controller = new AbortController();
    pending.add(controller);
    const payload: PostHogCapturePayload = {
      api_key: token,
      event: name,
      distinct_id: id,
      properties: { ...properties, $geoip_disable: true, environment: analyticsEnvironment() },
    };
    try {
      void fetcher(POSTHOG_CAPTURE_URL, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload),
          credentials: "omit",
          keepalive: true,
          referrerPolicy: "no-referrer",
          signal: controller.signal,
        }).catch(() => undefined).finally(() => pending.delete(controller));
    } catch {
      pending.delete(controller);
    }
  }

  return {
    isConfigured: Boolean(token),
    distinctId(): string | null {
      return enabled ? distinctId : null;
    },
    customerType(): AnalyticsCustomerType {
      return enabled ? customerType : "guest";
    },
    resetIdentity(): void {
      if (enabled && token) {
        distinctId = createDistinctId();
        customerType = "guest";
      }
    },
    identify(customerId: string, options?: { created?: boolean }): void {
      const nextId = opaqueAnalyticsId(customerId);
      if (!enabled || !token || !distinctId || !nextId || nextId === distinctId) return;
      const anonymousId = distinctId;
      const accountEvent = {
        name: options?.created ? "storefront_account_created" : "storefront_account_signed_in",
        properties: { method: "passwordless" as const, anonymous_id: anonymousId },
      };
      const sanitized = sanitizeAnalyticsEvent(accountEvent);
      if (!sanitized) return;
      distinctId = nextId;
      customerType = options?.created ? "new" : "returning";
      send(sanitized.name, { ...sanitized.properties, $anon_distinct_id: anonymousId }, nextId);
    },
    capture(event: StorefrontBrowserEvent): void {
      if (!enabled || !token || !distinctId) return;
      const sanitized = sanitizeAnalyticsEvent(event);
      if (!sanitized) return;
      send(sanitized.name, sanitized.properties, distinctId);
    },
    revoke(): void {
      enabled = false;
      distinctId = null;
      customerType = "guest";
      for (const controller of pending) controller.abort();
      pending.clear();
    },
  };
}

export function configuredPostHogBrowserProvider(): PostHogBrowserProvider {
  return createPostHogBrowserProvider({ projectToken: process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN });
}
