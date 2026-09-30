import { sanitizeAnalyticsEvent, type BrowserAnalyticsProvider, type StorefrontBrowserEvent } from "./events";

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
  resetIdentity(): void;
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
  let enabled = Boolean(token);

  return {
    isConfigured: Boolean(token),
    resetIdentity(): void {
      if (enabled && token) distinctId = createDistinctId();
    },
    capture(event: StorefrontBrowserEvent): void {
      if (!enabled || !token || !distinctId) return;
      const sanitized = sanitizeAnalyticsEvent(event);
      if (!sanitized) return;
      const controller = new AbortController();
      pending.add(controller);
      const payload: PostHogCapturePayload = {
        api_key: token,
        event: sanitized.name,
        distinct_id: distinctId,
        properties: sanitized.properties,
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
    },
    revoke(): void {
      enabled = false;
      distinctId = null;
      for (const controller of pending) controller.abort();
      pending.clear();
    },
  };
}

export function configuredPostHogBrowserProvider(): PostHogBrowserProvider {
  return createPostHogBrowserProvider({ projectToken: process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN });
}
