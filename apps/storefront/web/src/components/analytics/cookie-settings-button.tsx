"use client";

import { useStorefrontAnalytics } from "./analytics-provider";

export function CookieSettingsButton({ className }: { className?: string }) {
  const { openPrivacySettings } = useStorefrontAnalytics();
  return <button type="button" className={className} onClick={openPrivacySettings}>Cookie settings</button>;
}
