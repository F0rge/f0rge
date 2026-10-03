import type { Metadata } from "next";
import Link from "next/link";
import { ClerkProvider } from "@clerk/nextjs";
import { UiProvider } from "@f0rge/ui";
import { StorefrontAnalyticsProvider } from "@/components/analytics/analytics-provider";
import { HeaderAuth } from "@/components/header-auth";
import "./style.css";

const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3004";
const indexable = process.env.STOREFRONT_INDEXING_ENABLED === "true" &&
  process.env.RAILWAY_ENVIRONMENT_NAME === "production" &&
  new URL(baseUrl).protocol === "https:";

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),
  title: { default: "The Collector | Considered furniture", template: "%s | The Collector" },
  description: "Considered furniture and objects for a life in colour.",
  alternates: { canonical: "/" },
  robots: { index: indexable, follow: indexable },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const clerkConfigured = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY && process.env.STOREFRONT_CLERK_JWT_TEMPLATE);
  const storefront = <UiProvider><StorefrontAnalyticsProvider>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <div className="announcement">A considered collection for everyday living</div>
    <header className="site-header"><Link href="/" className="wordmark" aria-label="The Collector home">THE COLLECTOR</Link><nav aria-label="Main navigation"><Link href="/shop">Shop all</Link><Link href="/collections">Collections</Link><Link href="/bag">Bag</Link><Link href="/account">Account</Link>{clerkConfigured ? <HeaderAuth /> : null}</nav><Link href="/shop" className="header-cta">Explore pieces <span aria-hidden="true">↗</span></Link></header>
    <main id="main-content">{children}</main>
    <footer className="site-footer"><Link href="/" className="wordmark">THE COLLECTOR</Link><p>Objects for a life in colour.</p><Link href="/shop">Shop the collection ↗</Link></footer>
  </StorefrontAnalyticsProvider></UiProvider>;
  return <html lang="en-ZA"><body>{clerkConfigured ? <ClerkProvider publishableKey={process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}>{storefront}</ClerkProvider> : storefront}</body></html>;
}
