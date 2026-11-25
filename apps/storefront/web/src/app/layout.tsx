import type { Metadata } from "next";
import localFont from "next/font/local";
import { ClerkProvider } from "@clerk/nextjs";
import { UiProvider } from "@f0rge/ui";
import { StorefrontAnalyticsProvider } from "@/components/analytics/analytics-provider";
import { BagProvider } from "@/components/bag";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { collectorSkinAttribute } from "@/lib/collector-skin";
import { currentCustomerPolicies } from "@/lib/customer-policies";
import { storefrontIndexable } from "@/lib/launch-indexing";
import "./style.css";

const instrumentSerif = localFont({
  src: "../fonts/InstrumentSerif-Regular.ttf",
  variable: "--daskasas-serif",
  display: "swap",
});

const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3004";
const indexable = storefrontIndexable();
const skin = collectorSkinAttribute(currentCustomerPolicies()?.collector_skin ?? null);

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),
  title: { default: "DasKasas | Considered furniture", template: "%s | DasKasas" },
  description: "Discover DasKasas furniture online and visit our Bedford Square showroom in Bedfordview, Johannesburg. Browse the collection and check availability.",
  alternates: { canonical: "/" },
  robots: { index: indexable, follow: indexable },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const clerkConfigured = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY && process.env.STOREFRONT_CLERK_JWT_TEMPLATE);
  const storefront = <UiProvider><StorefrontAnalyticsProvider><BagProvider>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <SiteHeader clerkConfigured={clerkConfigured} />
    <main id="main-content">{children}</main>
    <SiteFooter />
  </BagProvider></StorefrontAnalyticsProvider></UiProvider>;
  return <html lang="en-ZA" className={instrumentSerif.variable} data-scroll-behavior="smooth" data-collector-skin={skin ?? undefined}><body>{clerkConfigured ? <ClerkProvider publishableKey={process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY} appearance={{ variables: { colorPrimary: "var(--primary)", fontFamily: "var(--sans)", borderRadius: "10px" } }}>{storefront}</ClerkProvider> : storefront}</body></html>;
}
