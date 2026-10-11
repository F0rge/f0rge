import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { UiProvider } from "@f0rge/ui";
import { StorefrontAnalyticsProvider } from "@/components/analytics/analytics-provider";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { collectorSkinAttribute } from "@/lib/collector-skin";
import { currentCustomerPolicies } from "@/lib/customer-policies";
import { storefrontIndexable } from "@/lib/launch-indexing";
import "./style.css";

const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3004";
const indexable = storefrontIndexable();
const skin = collectorSkinAttribute(currentCustomerPolicies()?.collector_skin ?? null);

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),
  title: { default: "Vellano | Considered furniture", template: "%s | Vellano" },
  description: "Considered furniture for a home, thoughtfully yours.",
  alternates: { canonical: "/" },
  robots: { index: indexable, follow: indexable },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const clerkConfigured = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY && process.env.STOREFRONT_CLERK_JWT_TEMPLATE);
  const storefront = <UiProvider><StorefrontAnalyticsProvider>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <SiteHeader clerkConfigured={clerkConfigured} />
    <main id="main-content">{children}</main>
    <SiteFooter />
  </StorefrontAnalyticsProvider></UiProvider>;
  return <html lang="en-ZA" data-scroll-behavior="smooth" data-collector-skin={skin ?? undefined}><body>{clerkConfigured ? <ClerkProvider publishableKey={process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY} appearance={{ variables: { colorPrimary: "var(--primary)", fontFamily: "var(--sans)", borderRadius: "10px" } }}>{storefront}</ClerkProvider> : storefront}</body></html>;
}
