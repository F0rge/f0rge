import { describe, expect, it } from "vitest";
import { formatZar } from "./order-money";
import {
  POLICY_PLACEHOLDERS,
  currentCustomerPolicies,
  policyPage,
  type CustomerPolicyDocument,
  type PolicyView,
} from "./customer-policies";

const reviewed: CustomerPolicyDocument = {
  legal_name: "Northwind Furnishings (Pty) Ltd",
  trading_name: "Northwind",
  contact_address: "12 Commerce Road, Kramerville, Johannesburg, 2090",
  support_mailbox: "support@northwind.co.za",
  phone: "011 555 0100",
  company_registration_number: "2020/123456/07",
  vat_registered: true,
  vat_number: "4123456789",
  delivery: "Delivery is available in the approved Gauteng zones at the stated VAT-inclusive rate.",
  collection_location: "Kramerville showroom, 12 Commerce Road, Johannesburg",
  collection_instructions: "Collect from the showroom desk on weekdays between 09:00 and 16:00.",
  gauteng_zones: [{ name: "Johannesburg", rate_zar_incl_vat: "950.00" }],
  terms: "Owner terms.",
  refund_policy: "Owner refund text for standard made to order pieces. Bespoke commissions use a separate agreement.",
  return_policy: "Owner return text. Standard made to order pieces keep the confirmed lead time. Bespoke commissions use a separate agreement.",
  privacy: "We use contact details to fulfil the order and to provide support.",
  data_collected: "Name, email, phone, and delivery address.",
  processors: "Clerk, PostHog, Peach, SendGrid, and Railway.",
  retention: "Order records follow tax law.",
  information_officer_name: "Naledi Dlamini",
  information_officer_responsibilities: "Receives privacy questions and PAIA requests sent to the support mailbox.",
  paia_baseline: "The information officer publishes the PAIA manual and acknowledges requests received at the support mailbox.",
  collector_skin: "Oxblood / citron",
  distinguishes_standard_made_to_order_from_bespoke: true,
};

function textOf(page: PolicyView): string {
  return page.blocks.map((block) => block.text).join("\n");
}

function sectionText(page: PolicyView, heading: string): string {
  const start = page.blocks.findIndex((block) => block.type === "heading" && block.text === heading);
  const next = page.blocks.findIndex((block, index) => index > start && block.type === "heading");
  return page.blocks.slice(start + 1, next === -1 ? undefined : next).map((block) => block.text).join("\n");
}

describe("customer policies", () => {
  it("publishes no owner identity while the launch pack is absent", () => {
    expect(currentCustomerPolicies()).toBeNull();
    const page = policyPage(null, "privacy");
    expect(page.published).toBe(false);
    expect(textOf(page)).toContain(POLICY_PLACEHOLDERS.legalName);
    expect(textOf(page)).toContain(POLICY_PLACEHOLDERS.informationOfficer);
    expect(textOf(page)).toContain(POLICY_PLACEHOLDERS.paia);
    expect(textOf(page)).toContain("POPIA");
    expect(textOf(page)).toContain("Clerk");
    expect(textOf(page)).toContain("PostHog");
    expect(textOf(page)).toContain("Peach");
    expect(textOf(page)).toContain("SendGrid");
    expect(textOf(page)).toContain("Railway");
    expect(textOf(page)).not.toContain("@");
    expect(textOf(page).toLowerCase()).not.toContain("northwind");
  });

  it("fills return and refund rules without placeholders, and keeps delivery and contact unmarked", () => {
    const returns = policyPage(null, "returns");
    const refunds = policyPage(null, "refunds");
    const terms = policyPage(null, "terms");
    for (const page of [returns, refunds]) {
      expect(page.published).toBe(false);
      expect(textOf(page)).not.toContain("[PLACEHOLDER:");
      expect(textOf(page)).toContain("30 days");
      expect(textOf(page)).toContain("made-to-order");
      expect(textOf(page)).toContain("bespoke");
      expect(textOf(page)).toContain("Consumer Protection Act");
    }
    expect(textOf(returns)).toContain("collection fee");
    expect(textOf(returns)).toContain("12 months");
    expect(textOf(returns)).toContain("6 months");
    expect(textOf(refunds)).toContain("10 working days");
    expect(textOf(refunds)).toContain("Peach Payments");
    expect(sectionText(terms, "Returns and refunds")).not.toContain("[PLACEHOLDER:");
    expect(sectionText(terms, "Returns and refunds")).toContain("made-to-order");
    expect(sectionText(terms, "Returns and refunds")).toContain("bespoke");
    expect(textOf(policyPage(null, "delivery"))).toContain(POLICY_PLACEHOLDERS.delivery);
    expect(textOf(policyPage(null, "delivery"))).not.toMatch(/R\s?\d/);
    expect(textOf(policyPage(null, "contact"))).toContain(POLICY_PLACEHOLDERS.email);
    expect(textOf(policyPage(null, "contact"))).toContain(POLICY_PLACEHOLDERS.phone);
    expect(textOf(policyPage(null, "contact"))).toContain(POLICY_PLACEHOLDERS.address);
    expect(textOf(policyPage(null, "contact"))).not.toContain("@");
  });

  it("shows reviewed contact, delivery, return, and privacy text only from the supplied document", () => {
    expect(textOf(policyPage(reviewed, "returns"))).toContain(reviewed.return_policy);
    expect(textOf(policyPage(reviewed, "returns"))).not.toContain("30 days");
    expect(textOf(policyPage(reviewed, "refunds"))).toContain(reviewed.refund_policy);
    expect(textOf(policyPage(reviewed, "contact"))).toContain("011 555 0100");
    expect(textOf(policyPage(reviewed, "contact"))).toContain("2020/123456/07");
    expect(textOf(policyPage(reviewed, "contact"))).toContain("support@northwind.co.za");
    expect(textOf(policyPage(reviewed, "delivery"))).toContain(formatZar("950.00"));
    expect(textOf(policyPage(reviewed, "privacy"))).toContain("Naledi Dlamini");
    expect(textOf(policyPage(reviewed, "privacy"))).toContain(reviewed.processors);
    const terms = policyPage(reviewed, "terms");
    expect(terms.published).toBe(true);
    expect(textOf(terms)).toContain(reviewed.terms);
    expect(textOf(terms)).not.toContain("30 days");
  });
});
