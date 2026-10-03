export type AnalyticsConsentChoice = "accepted" | "rejected";

export interface ConsentStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export const ANALYTICS_CONSENT_STORAGE_KEY = "storefront-analytics-consent-v1";

export function loadAnalyticsConsent(storage: ConsentStorage | null): AnalyticsConsentChoice | null {
  if (!storage) return null;
  try {
    const choice = storage.getItem(ANALYTICS_CONSENT_STORAGE_KEY);
    return choice === "accepted" || choice === "rejected" ? choice : null;
  } catch {
    return null;
  }
}

export function saveAnalyticsConsent(storage: ConsentStorage | null, choice: AnalyticsConsentChoice): void {
  if (!storage) return;
  try {
    storage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, choice);
  } catch { /* Consent still applies for this page when storage is blocked. */ }
}
