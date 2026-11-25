import { currentCustomerPolicies } from "./customer-policies";

const CANONICAL_HOMEPAGE = "https://www.daskasas.co.za/";
const SITE_NAME = "DasKasas";
export const ORGANIZATION_LOGO_PATH = "/apple-icon";

export function homepageStructuredData(env: Record<string, string | undefined> = process.env): string | null {
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
    ],
  };

  // JSON inside a script element must not contain a literal HTML closing tag.
  return JSON.stringify(structuredData).replace(/</g, "\\u003c");
}
