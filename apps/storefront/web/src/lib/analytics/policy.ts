/** EU project 292683. Public project id only — never a personal or ingestion secret. */
export const POSTHOG_EU_PROJECT_ID = "292683";
export const POSTHOG_EU_INGEST_HOST = "https://eu.i.posthog.com";

/**
 * Baselines checked against PostHog Cloud docs on 2026-10-03.
 * Retention cannot be shortened to delete data. A billing alert does not drop ingestion.
 * A per-product billing limit does. Replay on the free plan is 30 days, not one year.
 */
export const ANALYTICS_POLICY = {
  projectId: POSTHOG_EU_PROJECT_ID,
  ingestHost: POSTHOG_EU_INGEST_HOST,
  region: "eu",
  analyticsRetention: "P1Y",
  replayRetention: "P30D",
  retentionIsNotDeletion: true,
  deletion: "person_and_recordings",
  export: "batch_export_and_recording_json",
  analyticsBillingLimitUsd: 5,
  platformBudgetUsd: 50,
  billingAlertIsHardCap: false,
  billingLimitDropsIngestion: true,
  alertThresholds: [0.7, 0.9],
  freeMonthlyEvents: 1_000_000,
  freeMonthlyRecordings: 5_000,
  replaySampleRate: 0.1,
  geoipEnrichment: "disabled",
  ipRetention: "disabled",
  testTrafficProperty: "environment",
  testTrafficValue: "test",
} as const;

export function analyticsEnvironment(): "production" | "test" {
  if (process.env.NEXT_PUBLIC_STOREFRONT_ANALYTICS_ENV === "production") return "production";
  if (process.env.STOREFRONT_RUNTIME_KIND === "production") return "production";
  return "test";
}
