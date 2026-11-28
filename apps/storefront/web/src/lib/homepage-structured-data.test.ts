import { beforeEach, describe, expect, it, vi } from "vitest";
import { currentCustomerPolicies } from "./customer-policies";
import { homepageStructuredData } from "./homepage-structured-data";

vi.mock("./customer-policies", async (importOriginal) => {
  const original = await importOriginal<typeof import("./customer-policies")>();
  return { ...original, currentCustomerPolicies: vi.fn(original.currentCustomerPolicies) };
});

const PRODUCTION_ENV = {
  RAILWAY_ENVIRONMENT_NAME: "production",
  STOREFRONT_PRIVATE_PREVIEW: "off",
  NEXT_PUBLIC_BASE_URL: "https://www.daskasas.co.za",
};

describe("homepage structured data", () => {
  beforeEach(() => vi.mocked(currentCustomerPolicies).mockReset());

  it("identifies the website, organization and public showroom while the policy is unpublished", () => {
    vi.mocked(currentCustomerPolicies).mockReturnValue(null);
    expect(JSON.parse(homepageStructuredData(PRODUCTION_ENV) ?? "null")).toEqual({
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "Organization",
          "@id": "https://www.daskasas.co.za/#organization",
          name: "DasKasas",
          url: "https://www.daskasas.co.za/",
          logo: "https://www.daskasas.co.za/apple-icon",
        },
        {
          "@type": "WebSite",
          "@id": "https://www.daskasas.co.za/#website",
          name: "DasKasas",
          url: "https://www.daskasas.co.za/",
          publisher: { "@id": "https://www.daskasas.co.za/#organization" },
        },
        {
          "@type": "FurnitureStore",
          "@id": "https://www.daskasas.co.za/#showroom",
          name: "DasKasas, Bedford Square",
          url: "https://www.daskasas.co.za/#visit",
          parentOrganization: { "@id": "https://www.daskasas.co.za/#organization" },
          telephone: "+27 10 745 1980",
          address: {
            "@type": "PostalAddress",
            streetAddress: "Shop GL15, Bedford Square, Smith Road",
            addressLocality: "Bedfordview",
            addressRegion: "Gauteng",
            postalCode: "2007",
            addressCountry: "ZA",
          },
          openingHoursSpecification: [
            {
              "@type": "OpeningHoursSpecification",
              dayOfWeek: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
              opens: "09:00:00",
              closes: "18:00:00",
            },
            { "@type": "OpeningHoursSpecification", dayOfWeek: ["Saturday"], opens: "09:00:00", closes: "17:00:00" },
            { "@type": "OpeningHoursSpecification", dayOfWeek: ["Sunday"], opens: "09:00:00", closes: "15:00:00" },
          ],
        },
      ],
    });
  });

  it.each([
    ["NEXT_PUBLIC_BASE_URL", undefined],
    ["NEXT_PUBLIC_BASE_URL", "http://www.daskasas.co.za"],
    ["NEXT_PUBLIC_BASE_URL", "https://www.daskasas.co.za/preview"],
    ["NEXT_PUBLIC_BASE_URL", "https://www.daskasas.co.za.preview.example"],
    ["RAILWAY_ENVIRONMENT_NAME", "preview"],
    ["STOREFRONT_PRIVATE_PREVIEW", "on"],
  ] as const)("omits markup when %s is %s", (key, value) => {
    expect(homepageStructuredData({ ...PRODUCTION_ENV, [key]: value })).toBeNull();
  });

  it("includes only approved public company facts and escapes HTML delimiters", () => {
    const approvedPolicy = currentCustomerPolicies();
    if (!approvedPolicy) throw new Error("Expected approved company details");
    const legalName = "Example </script> (Pty) Ltd";
    vi.mocked(currentCustomerPolicies).mockReturnValue({ ...approvedPolicy, legal_name: legalName });

    const markup = homepageStructuredData(PRODUCTION_ENV) ?? "";
    expect(markup).not.toContain("<");
    expect(JSON.parse(markup)["@graph"][0]).toMatchObject({ legalName });
    expect(markup).not.toContain(approvedPolicy.information_officer_name);
  });
});
