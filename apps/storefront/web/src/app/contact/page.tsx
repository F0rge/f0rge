import type { Metadata } from "next";
import { PolicyArticle } from "@/components/policy-article";
import { currentCustomerPolicies, policyPage } from "@/lib/customer-policies";
import { storefrontIndexable } from "@/lib/launch-indexing";

const page = policyPage(currentCustomerPolicies(), "contact");
const index = storefrontIndexable() && page.published;

export const metadata: Metadata = {
  title: page.title,
  robots: { index, follow: index },
  alternates: { canonical: "/contact" },
};

export default function ContactPage() {
  return <PolicyArticle page={page} section="contact" />;
}
