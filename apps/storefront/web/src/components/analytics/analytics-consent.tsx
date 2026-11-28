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

  function save(next: AnalyticsConsentChoice) {
    choose(next);
    setSettingsOpen(false);
  }

  return <section className={styles.panel} aria-labelledby="analytics-consent-title" aria-describedby="analytics-consent-description">
    <div className={styles.headingRow}>
      <h2 id="analytics-consent-title">Your privacy choices</h2>
      {choice && <button className={styles.closeButton} type="button" onClick={() => setSettingsOpen(false)} aria-label="Close privacy settings">×</button>}
    </div>
    <p id="analytics-consent-description">
      {choice ? `Optional analytics is ${choice === "accepted" ? "on" : "off"}.` : "Allow optional analytics to help us improve the shop?"} <Link href="/policies/privacy">Privacy notice</Link>
    </p>
    {!analyticsConfigured && <p className={styles.status}>Optional analytics is not configured yet.</p>}
    <div className={styles.actions}>
      {choice === "accepted" ? <button type="button" onClick={() => save("rejected")}>
        Withdraw optional analytics
      </button> : <>
        {choice === "rejected"
          ? <button type="button" onClick={() => setSettingsOpen(false)}>Keep analytics off</button>
          : <button type="button" aria-label="Reject optional analytics" onClick={() => save("rejected")}>Reject</button>}
        <button type="button" aria-label="Accept optional analytics" onClick={() => save("accepted")}>Accept</button>
      </>}
    </div>
  </section>;
}
