export type CustomerPolicyDocument = {
  legal_name: string;
  trading_name: string;
  contact_address: string;
  support_mailbox: string;
  delivery: string;
  collection_location: string;
  collection_instructions: string;
  gauteng_zones: { name: string; rate_zar_incl_vat: string }[];
  cancellation_returns_refund: string;
  privacy: string;
  information_officer_name: string;
  information_officer_responsibilities: string;
  paia_baseline: string;
  collector_skin: string;
  distinguishes_standard_made_to_order_from_bespoke: true;
};

export type PolicySection = "support" | "delivery" | "returns" | "privacy";

const UNPUBLISHED = "Reviewed text for this page is not published.";

const TITLES: Record<PolicySection, string> = {
  support: "Support",
  delivery: "Delivery and collection",
  returns: "Returns and refunds",
  privacy: "Privacy",
};

export function currentCustomerPolicies(): CustomerPolicyDocument | null {
  // The owner launch pack is not in this repository. Do not substitute copy.
  return null;
}

export function policyPage(document: CustomerPolicyDocument | null, section: PolicySection): {
  title: string;
  published: boolean;
  paragraphs: string[];
} {
  if (!document) return { title: TITLES[section], published: false, paragraphs: [UNPUBLISHED] };
  if (section === "support") {
    return {
      title: TITLES.support,
      published: true,
      paragraphs: [document.legal_name, document.trading_name, document.contact_address, document.support_mailbox],
    };
  }
  if (section === "delivery") {
    return {
      title: TITLES.delivery,
      published: true,
      paragraphs: [
        document.delivery,
        document.collection_location,
        document.collection_instructions,
        ...document.gauteng_zones.map((zone) => `${zone.name}: R${zone.rate_zar_incl_vat} incl. VAT`),
      ],
    };
  }
  if (section === "returns") {
    return { title: TITLES.returns, published: true, paragraphs: [document.cancellation_returns_refund] };
  }
  return {
    title: TITLES.privacy,
    published: true,
    paragraphs: [
      document.privacy,
      document.information_officer_name,
      document.information_officer_responsibilities,
      document.paia_baseline,
    ],
  };
}
