import { describe, expect, it } from "vitest";
import { currentCustomerPolicies, policyPage } from "./customer-policies";

const reviewed = {
  legal_name: "Northwind Furnishings (Pty) Ltd",
  trading_name: "Northwind",
  contact_address: "12 Commerce Road, Kramerville, Johannesburg, 2090",
  support_mailbox: "support@northwind.co.za",
  delivery: "Delivery is available in the approved Gauteng zones at the stated VAT-inclusive rate.",
  collection_location: "Kramerville showroom, 12 Commerce Road, Johannesburg",
  collection_instructions: "Collect from the showroom desk on weekdays between 09:00 and 16:00.",
  gauteng_zones: [{ name: "Johannesburg", rate_zar_incl_vat: "950.00" }],
  cancellation_returns_refund: "Standard made to order pieces keep the confirmed lead time on the order. Bespoke commissions are not offered on the storefront and use a separate agreement.",
  privacy: "We use contact details to fulfil the order and to provide support. Optional analytics stay off until the visitor accepts them.",
  information_officer_name: "Naledi Dlamini",
  information_officer_responsibilities: "Receives privacy questions and PAIA requests sent to the support mailbox.",
  paia_baseline: "The information officer publishes the PAIA manual and acknowledges requests received at the support mailbox.",
  collector_skin: "Oxblood / citron",
  distinguishes_standard_made_to_order_from_bespoke: true as const,
};

describe("customer policies", () => {
  it("publishes no owner text while the launch pack is absent", () => {
    expect(currentCustomerPolicies()).toBeNull();
    const page = policyPage(null, "privacy");
    expect(page.published).toBe(false);
    expect(page.paragraphs).toEqual(["Reviewed text for this page is not published."]);
    expect(JSON.stringify(page)).not.toContain("northwind");
    expect(JSON.stringify(page)).not.toContain("@");
  });

  it("shows the reviewed returns text that separates made to order from bespoke", () => {
    const page = policyPage(reviewed, "returns");
    expect(page.published).toBe(true);
    expect(page.paragraphs).toEqual([reviewed.cancellation_returns_refund]);
    expect(page.paragraphs[0]).toContain("made to order");
    expect(page.paragraphs[0]).toContain("Bespoke");
  });

  it("shows support contact and delivery rates only from the reviewed document", () => {
    expect(policyPage(reviewed, "support").paragraphs).toEqual([
      "Northwind Furnishings (Pty) Ltd",
      "Northwind",
      "12 Commerce Road, Kramerville, Johannesburg, 2090",
      "support@northwind.co.za",
    ]);
    expect(policyPage(reviewed, "delivery").paragraphs).toEqual([
      reviewed.delivery,
      "Kramerville showroom, 12 Commerce Road, Johannesburg",
      "Collect from the showroom desk on weekdays between 09:00 and 16:00.",
      "Johannesburg: R950.00 incl. VAT",
    ]);
    expect(policyPage(reviewed, "privacy").paragraphs).toEqual([
      reviewed.privacy,
      "Naledi Dlamini",
      reviewed.information_officer_responsibilities,
      reviewed.paia_baseline,
    ]);
  });
});
