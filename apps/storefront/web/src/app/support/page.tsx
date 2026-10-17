import type { Metadata } from "next";
import { PolicyArticle } from "@/components/policy-article";
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
  return <PolicyArticle page={page} section="support" />;
}
