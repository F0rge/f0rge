import type { Metadata } from "next";
import { currentCustomerPolicies, policyPage } from "@/lib/customer-policies";
import { storefrontIndexable } from "@/lib/launch-indexing";

const page = policyPage(currentCustomerPolicies(), "support");
const index = storefrontIndexable() && page.published;

export const metadata: Metadata = {
  title: page.title,
  robots: { index, follow: index },
  alternates: { canonical: "/support" },
};

export default function SupportPage() {
  return <article className="content policy-page">
    <p className="eyebrow">The Collector</p>
    <h1>{page.title}</h1>
    {page.paragraphs.map((paragraph, index) => <p key={`support-${index}`}>{paragraph}</p>)}
  </article>;
}
