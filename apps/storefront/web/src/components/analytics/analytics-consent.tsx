"use client";

import Link from "next/link";
import type { AnalyticsConsentChoice } from "@/lib/analytics/consent";
import styles from "./analytics-consent.module.css";

const analyticsConfigured = Boolean(process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN?.trim());

export function AnalyticsConsentPanel({ choice, ready, choose, settingsOpen, setSettingsOpen }: {
  choice: AnalyticsConsentChoice | null;
  ready: boolean;
  choose(choice: AnalyticsConsentChoice): void;
  settingsOpen: boolean;
  setSettingsOpen(open: boolean): void;
}) {
  // Once chosen, the footer's "Cookie settings" reopens this; no floating control covers page content or the bag drawer.
  if (!ready || (choice && !settingsOpen)) return null;

  return <section className={styles.panel} aria-labelledby="analytics-consent-title" aria-describedby="analytics-consent-description">
    <div className={styles.headingRow}>
      <h2 id="analytics-consent-title">Your privacy choices</h2>
      {choice && <button className={styles.closeButton} type="button" onClick={() => setSettingsOpen(false)} aria-label="Close privacy settings">×</button>}
    </div>
    <p id="analytics-consent-description">
      Optional analytics helps us understand which pieces and shop filters are useful. It stays off until you allow it. We never send search text, personal details or payment data. <Link href="/policies/privacy">Read the privacy notice</Link> before you choose.
    </p>
    {!analyticsConfigured && <p className={styles.status}>Optional analytics is not configured yet.</p>}
    <div className={styles.actions}>
      {choice === "accepted" ? <button className={styles.primaryButton} type="button" onClick={() => { choose("rejected"); setSettingsOpen(false); }}>
        Withdraw optional analytics
      </button> : <button className={styles.primaryButton} type="button" onClick={() => { choose("accepted"); setSettingsOpen(false); }}>
        Accept optional analytics
      </button>}
      {choice === null && <button className={styles.primaryButton} type="button" onClick={() => choose("rejected")}>
        Reject optional analytics
      </button>}
      {choice === "rejected" && <button className={styles.secondaryButton} type="button" onClick={() => setSettingsOpen(false)}>
        Keep analytics off
      </button>}
    </div>
  </section>;
}
