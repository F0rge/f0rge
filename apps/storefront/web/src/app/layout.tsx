import type { Metadata } from "next";
import localFont from "next/font/local";
import { IBM_Plex_Mono, IBM_Plex_Sans, Source_Serif_4 } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { UiProvider } from "@f0rge/ui";
import { StorefrontAnalyticsProvider } from "@/components/analytics/analytics-provider";
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

// next/font downloads these at build time and serves them from this origin; no runtime third-party font request.
const sourceSerif = Source_Serif_4({ subsets: ["latin"], weight: ["400", "600"], style: "normal", variable: "--daskasas-heading", display: "swap" });
const plexSans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500"], variable: "--daskasas-sans", display: "swap" });
const plexMono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--daskasas-mono", display: "swap" });

const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3004";
const indexable = storefrontIndexable();
const skin = collectorSkinAttribute(currentCustomerPolicies()?.collector_skin ?? null);

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),
  title: { default: "DasKasas | Considered furniture", template: "%s | DasKasas" },
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
  return <html lang="en-ZA" className={`${instrumentSerif.variable} ${sourceSerif.variable} ${plexSans.variable} ${plexMono.variable}`} data-scroll-behavior="smooth" data-collector-skin={skin ?? undefined}><body>{clerkConfigured ? <ClerkProvider publishableKey={process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY} appearance={{ variables: { colorPrimary: "var(--primary)", colorForeground: "var(--foreground)", colorMutedForeground: "var(--muted-foreground)", colorBackground: "var(--background)", colorInput: "var(--plate)", colorInputForeground: "var(--foreground)", colorDanger: "var(--destructive)", fontFamily: "var(--sans)", borderRadius: "0" } }}>{storefront}</ClerkProvider> : storefront}</body></html>;
}
