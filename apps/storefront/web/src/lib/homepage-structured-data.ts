import { currentCustomerPolicies } from "./customer-policies";
import { SHOWROOM } from "./showroom";

const CANONICAL_HOMEPAGE = "https://www.daskasas.co.za/";
const SITE_NAME = "DasKasas";
export const ORGANIZATION_LOGO_PATH = "/apple-icon";

// Next.js inlines the public canonical URL at build time. Deployment guards are read at runtime.
export function homepageStructuredData(env: Record<string, string | undefined> = {
  RAILWAY_ENVIRONMENT_NAME: process.env.RAILWAY_ENVIRONMENT_NAME,
  STOREFRONT_PRIVATE_PREVIEW: process.env.STOREFRONT_PRIVATE_PREVIEW,
  NEXT_PUBLIC_BASE_URL: process.env.NEXT_PUBLIC_BASE_URL,
}): string | null {
  if (env.RAILWAY_ENVIRONMENT_NAME !== "production" || env.STOREFRONT_PRIVATE_PREVIEW !== "off") return null;
  const homepage = URL.parse(env.NEXT_PUBLIC_BASE_URL || "");
  if (!homepage || homepage.href !== CANONICAL_HOMEPAGE) return null;

  const legalName = currentCustomerPolicies()?.legal_name;
  const organizationId = `${homepage.href}#organization`;
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": organizationId,
        name: SITE_NAME,
        url: homepage.href,
        logo: new URL(ORGANIZATION_LOGO_PATH, homepage).href,
        ...(legalName ? { legalName } : {}),
      },
      {
        "@type": "WebSite",
        "@id": `${homepage.href}#website`,
        name: SITE_NAME,
        url: homepage.href,
        publisher: { "@id": organizationId },
      },
      {
        "@type": "FurnitureStore",
        "@id": `${homepage.href}#showroom`,
        name: SHOWROOM.name,
        url: new URL("#visit", homepage).href,
        parentOrganization: { "@id": organizationId },
        address: { "@type": "PostalAddress", ...SHOWROOM.postalAddress },
        telephone: SHOWROOM.telephone,
        openingHoursSpecification: SHOWROOM.hours.map(({ dayOfWeek, opens, closes }) => ({
          "@type": "OpeningHoursSpecification",
          dayOfWeek,
          opens: `${opens}:00`,
          closes: `${closes}:00`,
        })),
      },
    ],
  };

  // JSON inside a script element must not contain a literal HTML closing tag.
  return JSON.stringify(structuredData).replace(/</g, "\\u003c");
}
