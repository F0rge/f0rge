import { POSTHOG_EU_HOST } from "./posthog-browser";
import type { AnalyticsConsentChoice } from "./consent";

export const REPLAY_SAMPLE_SPACE = 1000;
export const REPLAY_SAMPLE_THRESHOLD = 100;

export type ReplayVendorConfig = {
  api_host: typeof POSTHOG_EU_HOST;
  autocapture: false;
  capture_pageview: false;
  capture_pageleave: false;
  capture_exceptions: false;
  disable_session_recording: false;
  ip: false;
  enable_recording_console_log: false;
  session_recording: {
    sampleRate: 0.1;
    maskAllInputs: true;
    maskTextSelector: "*";
    blockSelector: "[data-storefront-no-capture]";
    recordCrossOriginIframes: false;
    recordHeaders: false;
    recordBody: false;
  };
};

/** Explicit vendor settings. Masking defaults are not the control. */
export const REPLAY_VENDOR_CONFIG: ReplayVendorConfig = {
  api_host: POSTHOG_EU_HOST,
  autocapture: false,
  capture_pageview: false,
  capture_pageleave: false,
  capture_exceptions: false,
  disable_session_recording: false,
  ip: false,
  enable_recording_console_log: false,
  session_recording: {
    sampleRate: 0.1,
    maskAllInputs: true,
    maskTextSelector: "*",
    blockSelector: "[data-storefront-no-capture]",
    recordCrossOriginIframes: false,
    recordHeaders: false,
    recordBody: false,
  },
};

export type ReplayDecision = {
  record: boolean;
  reason: "consented_sample" | "no_consent" | "not_sampled" | "blocked_route" | "sensitive_overlay" | "missing_session";
  config: ReplayVendorConfig | null;
};

const blockedRoute = /^\/(?:sign-in|sign-up|account|checkout|order)(?:\/|$)/;
const allowedRoute = /^\/(?:$|shop(?:\/|$)|collections(?:\/|$)|product(?:\/|$)|bag(?:\/|$))/;

export function replaySampleBucket(sessionKey: string): number {
  let hash = 2166136261;
  for (let index = 0; index < sessionKey.length; index += 1) {
    hash ^= sessionKey.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) % REPLAY_SAMPLE_SPACE;
}

export function isReplaySampled(sessionKey: string): boolean {
  return replaySampleBucket(sessionKey) < REPLAY_SAMPLE_THRESHOLD;
}

export function replayRouteAllowed(pathname: string): boolean {
  const path = pathname.split("?")[0]?.split("#")[0] || "/";
  if (blockedRoute.test(path)) return false;
  return allowedRoute.test(path);
}

export function decideReplay(input: {
  consent: AnalyticsConsentChoice | null;
  sessionKey: string | null;
  pathname: string;
  sensitiveOverlay: boolean;
}): ReplayDecision {
  if (input.consent !== "accepted") return { record: false, reason: "no_consent", config: null };
  if (!input.sessionKey) return { record: false, reason: "missing_session", config: null };
  if (!isReplaySampled(input.sessionKey)) return { record: false, reason: "not_sampled", config: null };
  if (input.sensitiveOverlay) return { record: false, reason: "sensitive_overlay", config: null };
  if (!replayRouteAllowed(input.pathname)) return { record: false, reason: "blocked_route", config: null };
  return { record: true, reason: "consented_sample", config: REPLAY_VENDOR_CONFIG };
}
