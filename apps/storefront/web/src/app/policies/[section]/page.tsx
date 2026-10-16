import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PolicyArticle } from "@/components/policy-article";
import { currentCustomerPolicies, policyPage, type PolicySection } from "@/lib/customer-policies";
import { storefrontIndexable } from "@/lib/launch-indexing";

const SECTIONS = new Set<PolicySection>(["delivery", "returns", "refunds", "terms", "privacy"]);

type PolicyPageProps = { params: Promise<{ section: string }> };

function sectionOf(value: string): PolicySection | null {
  return SECTIONS.has(value as PolicySection) ? value as PolicySection : null;
}

export async function generateMetadata({ params }: PolicyPageProps): Promise<Metadata> {
  const section = sectionOf((await params).section);
  if (!section) return {};
  const page = policyPage(currentCustomerPolicies(), section);
  const index = storefrontIndexable() && page.published;
  return {
    title: page.title,
    robots: { index, follow: index },
    alternates: { canonical: `/policies/${section}` },
  };
}

export default async function PolicySectionPage({ params }: PolicyPageProps) {
  const section = sectionOf((await params).section);
  if (!section) notFound();
  const page = policyPage(currentCustomerPolicies(), section);
  return <PolicyArticle page={page} section={section} />;
}
