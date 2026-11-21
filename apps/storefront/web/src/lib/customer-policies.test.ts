import { describe, expect, it } from "vitest";
import { formatZar } from "./order-money";
import { SHOWROOM } from "./showroom";
import {
  POLICY_PLACEHOLDERS,
  POLICY_REVIEW_NOTICE,
  currentCustomerPolicies,
  policyPage,
  RETURNS_SUMMARY,
  type CustomerPolicyDocument,
  type PolicyView,
} from "./customer-policies";

const reviewed: CustomerPolicyDocument = {
  legal_name: "Northwind Furnishings (Pty) Ltd",
  trading_name: "Northwind",
  legal_status: "Private company, registered in South Africa",
  office_bearers: ["Thandi Mokoena", "Pieter Botha"],
  legal_service_address: "14 Commerce Road, Kramerville, Johannesburg, 2090",
  codes_of_conduct: "Northwind subscribes to no code of conduct.",
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
  information_officer_name: "Naledi Dlamini",
  information_officer_email: "privacy@northwind.co.za",
  postal_address: "PO Box 1234, Kramerville, 2090",
  fax_number: "None",
  collector_skin: "Oxblood / citron",
  distinguishes_standard_made_to_order_from_bespoke: true,
};

const REGULATOR_EMAILS = ["enquiries@inforegulator.org.za", "POPIAComplaints@inforegulator.org.za"];

function emailsIn(text: string): string[] {
  return [...new Set(text.match(/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g) ?? [])];
}

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
    expect(textOf(page)).toContain(POLICY_PLACEHOLDERS.informationOfficerEmail);
    expect(textOf(page)).toContain("POPIA");
    for (const processor of ["Clerk", "PostHog", "Paystack", "SendGrid", "Railway"]) expect(textOf(page)).toContain(processor);
    // Only the showroom's public email and the Information Regulator's addresses appear before the owner document lands.
    expect(emailsIn(textOf(page))).toEqual([SHOWROOM.email, ...REGULATOR_EMAILS]);
    expect(textOf(page).toLowerCase()).not.toContain("northwind");
    for (const section of ["privacy", "paia"] as const) expect(policyPage(null, section).blocks[0]).toEqual({ type: "notice", text: POLICY_REVIEW_NOTICE });
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
    expect(textOf(refunds)).toContain("10 working days");
    expect(textOf(refunds)).toContain("Paystack");
    expect(sectionText(terms, "Cancellations and returns")).not.toContain("[PLACEHOLDER:");
    expect(sectionText(terms, "Cancellations and returns")).toContain("made-to-order");
    expect(sectionText(terms, "Cancellations and returns")).toContain("bespoke");
    expect(textOf(policyPage(null, "delivery"))).toContain(POLICY_PLACEHOLDERS.delivery);
    expect(textOf(policyPage(null, "delivery"))).not.toMatch(/R\s?\d/);
  });

  it("shows reviewed contact, delivery, privacy and business facts only from the supplied document", () => {
    expect(textOf(policyPage(reviewed, "delivery"))).toContain(formatZar("950.00"));
    expect(textOf(policyPage(reviewed, "delivery"))).toContain(reviewed.collection_location);
    for (const fact of ["Northwind Furnishings (Pty) Ltd", "Naledi Dlamini", "privacy@northwind.co.za", reviewed.contact_address]) {
      expect(textOf(policyPage(reviewed, "privacy"))).toContain(fact);
      expect(textOf(policyPage(reviewed, "paia"))).toContain(fact);
    }
    for (const fact of [reviewed.postal_address, "Fax: None.", "011 555 0100"]) expect(sectionText(policyPage(reviewed, "paia"), "Contact details of the head of DasKasas")).toContain(fact);
    const terms = policyPage(reviewed, "terms");
    expect(terms.published).toBe(true);
    for (const fact of ["Northwind Furnishings (Pty) Ltd", reviewed.legal_status, "2020/123456/07", "Thandi Mokoena, Pieter Botha", "4123456789", reviewed.contact_address, reviewed.legal_service_address, "011 555 0100", "support@northwind.co.za", reviewed.codes_of_conduct]) {
      expect(sectionText(terms, "Business information")).toContain(fact);
    }
    for (const section of ["terms", "returns", "refunds", "delivery", "privacy", "paia"] as const) {
      expect(policyPage(reviewed, section).published).toBe(true);
      expect(textOf(policyPage(reviewed, section))).not.toContain("[PLACEHOLDER:");
      expect(policyPage(reviewed, section).blocks.some((block) => block.type === "notice" && block.text.startsWith("Draft"))).toBe(false);
    }
  });

  it("lists every ECTA s43(1) business fact on the terms page, with identity facts placeholder-gated", () => {
    const terms = policyPage(null, "terms");
    expect(terms.published).toBe(false);
    expect(terms.blocks).toContainEqual({ type: "heading", text: "Business information", id: "business-information" });
    const business = sectionText(terms, "Business information");
    for (const placeholder of [
      POLICY_PLACEHOLDERS.legalName, // s43(1)(a)
      POLICY_PLACEHOLDERS.legalStatus, // s43(1)(a), (f) place of registration
      POLICY_PLACEHOLDERS.registration, // s43(1)(f)
      POLICY_PLACEHOLDERS.officeBearers, // s43(1)(f)
      POLICY_PLACEHOLDERS.legalServiceAddress, // s43(1)(g)
      POLICY_PLACEHOLDERS.codesOfConduct, // s43(1)(d), (e), (o)
      POLICY_PLACEHOLDERS.vat,
    ]) {
      expect(business).toContain(placeholder);
    }
    // s43(1)(b), (c): the showroom's public address, phones, email and the website.
    for (const fact of [SHOWROOM.address, "+27 63 025 4010", "010 745 1980", SHOWROOM.email, "www.daskasas.co.za"]) {
      expect(business).toContain(fact);
    }
    expect(textOf(terms).toLowerCase()).not.toContain("northwind");
  });

  it("covers every terms-of-sale section, the s43(2) review step and Paystack", () => {
    const terms = policyPage(null, "terms");
    const headings = terms.blocks.filter((block) => block.type === "heading").map((block) => block.text);
    expect(headings).toEqual([
      "Who these terms cover",
      "Business information",
      "Important terms",
      "Ordering",
      "Prices and VAT",
      "Payment",
      "Delivery and collection",
      "Risk and ownership",
      "Cancellations and returns",
      "Faults and guarantees",
      "Liability",
      "Privacy",
      "Governing law and complaints",
      "Contact",
    ]);
    expect(sectionText(terms, "Ordering")).toContain("You can go back and change anything, or leave without paying");
    expect(sectionText(terms, "Payment")).toContain("Paystack");
    expect(sectionText(terms, "Payment")).toContain("never see or store your full card number");
    expect(terms.links).toContainEqual({ href: "/policies/privacy", label: "Privacy" });
  });

  it("summarises returns for Help and the FAQ in line with the returns and refunds pages", () => {
    const returns = textOf(policyPage(null, "returns"));
    const refunds = textOf(policyPage(null, "refunds"));
    expect(RETURNS_SUMMARY.coolingOff).toContain("within 7 days after you receive the goods");
    expect(RETURNS_SUMMARY.coolingOff).toContain("including the delivery charge");
    expect(RETURNS_SUMMARY.coolingOff).toContain("only the direct cost of returning them");
    expect(RETURNS_SUMMARY.coolingOff).toContain("made to your specifications or clearly personalised");
    expect(returns).toContain("made to your specifications or clearly personalised");
    expect(RETURNS_SUMMARY.changeOfMind).toContain("within 30 days after delivery or collection");
    expect(returns).toContain("within 30 days after the day it is delivered or collected");
    expect(RETURNS_SUMMARY.changeOfMindCosts).toContain("For a change-of-mind return we refund the price of the piece and keep the original delivery charge");
    expect(refunds).toContain("Change of mind: the price of the piece. We keep the original delivery charge.");
    expect(Object.values(RETURNS_SUMMARY).join(" ")).not.toMatch(/delivery charge is not refunded/i);
  });

  it("states the CPA s56 fault right from delivery, the ECTA s44 cooling-off, and no 12-month or assessment-fee claims", () => {
    for (const section of ["terms", "returns", "refunds", "delivery"] as const) {
      for (const document of [null, reviewed]) {
        const text = textOf(policyPage(document, section));
        expect(text).not.toMatch(/12 months|twelve months/i);
        expect(text).not.toMatch(/assessment/i);
        expect(text).not.toMatch(/from the date of purchase/i);
        expect(text).not.toContain("Peach");
      }
    }
    for (const section of ["terms", "returns"] as const) {
      const text = textOf(policyPage(null, section));
      expect(text).toContain("within six months after delivery");
      expect(text).toContain("You pay no fee, and we carry the risk and cost of the return");
      expect(text).toContain("within 7 days after you receive the goods");
      expect(text).toContain("made to your specifications or clearly personalised");
    }
    expect(textOf(policyPage(null, "refunds"))).toContain("including the delivery charge");
  });

  it("gives every POPIA s18(1) item and the right to object in the privacy policy", () => {
    for (const document of [null, reviewed]) {
      const page = policyPage(document, "privacy");
      const text = textOf(page);
      // (a) information collected and its source when not from the customer.
      expect(sectionText(page, "What we collect")).toContain("When you check out: your name, email address and phone number");
      expect(sectionText(page, "What we collect")).toContain("From others: Paystack");
      // (b) name and address of the responsible party.
      expect(sectionText(page, "Who we are")).toContain(document ? reviewed.legal_name : POLICY_PLACEHOLDERS.legalName);
      expect(sectionText(page, "Who we are")).toContain(document ? reviewed.contact_address : SHOWROOM.address);
      // (c) purposes, with the s11 lawful basis.
      for (const basis of ["11(1)(a)", "11(1)(b)", "11(1)(c)", "11(1)(f)"]) expect(sectionText(page, "Why we use it")).toContain(basis);
      // (d), (e) voluntary or mandatory, and the consequences.
      expect(sectionText(page, "What you must give us")).toContain("Without them we cannot take, deliver or tell you about your order");
      expect(sectionText(page, "What you must give us")).toContain("optional");
      // (f) law requiring the collection.
      expect(sectionText(page, "Laws that require us to keep information")).toContain("Tax Administration Act 28 of 2011");
      // (g) cross-border transfers, where each processor is based, and the s72 ground.
      const transfers = sectionText(page, "Information sent outside South Africa");
      for (const ground of ["72(1)(a)", "72(1)(b)", "72(1)(c)"]) expect(transfers).toContain(ground);
      for (const [processor, place] of [["Paystack", "Nigeria"], ["SendGrid", "United States"], ["Clerk", "United States"], ["Railway", "United States"], ["PostHog", "European Union"]]) {
        expect(transfers).toMatch(new RegExp(`${processor}[^.]*${place}`));
        expect(sectionText(page, "Who we share it with")).toContain(processor);
      }
      // (h)(i)-(ii) recipients and categories; (iii) access and correction; (iv) objection; (v) the Regulator.
      expect(sectionText(page, "Your rights")).toContain("Access: you may ask, free of charge");
      expect(sectionText(page, "Your rights")).toContain("Correction and deletion");
      expect(sectionText(page, "Your right to object")).toContain("You have the right to object, at any time and free of charge");
      expect(sectionText(page, "How to make a request")).toContain("within 30 days");
      expect(sectionText(page, "Information Officer")).toContain(document ? "Naledi Dlamini" : POLICY_PLACEHOLDERS.informationOfficer);
      const regulator = sectionText(page, "Complaints to the Information Regulator");
      for (const fact of ["Woodmead North Office Park, 54 Maxwell Drive, Woodmead, Johannesburg, 2191", "010 023 5200", "0800 017 160", ...REGULATOR_EMAILS, "eservices.inforegulator.org.za"]) expect(regulator).toContain(fact);
      // s19 safeguards, retention and marketing only with opt-in.
      expect(sectionText(page, "How we protect it")).toContain("never see or store your full card number");
      expect(sectionText(page, "How long we keep it")).toContain("tax and accounting law");
      expect(sectionText(page, "Marketing")).toContain("unless you opt in");
      expect(sectionText(page, "Marketing")).toContain("never ticked for you");
      expect(text).not.toMatch(/JD House|Stiemens/);
      expect(page.links).toContainEqual({ href: "/policies/paia", label: "PAIA manual" });
    }
  });

  it("publishes a PAIA s51 manual with every required heading and no stale Regulator address", () => {
    for (const document of [null, reviewed]) {
      const page = policyPage(document, "paia");
      expect(page.title).toBe("PAIA manual");
      expect(page.blocks.filter((block) => block.type === "heading").map((block) => block.text)).toEqual([
        "About this manual",
        "Contact details of the head of DasKasas", // s51(1)(a)
        "The Information Regulator's PAIA Guide", // s51(1)(b)(i)
        "Records available without a request", // s51(1)(b)(ii)
        "Records kept under other laws", // s51(1)(b)(iii)
        "Subjects and categories of records", // s51(1)(b)(iv)
        "How to request a record",
        "Personal information we process", // s51(1)(c)
        "Availability of this manual", // s51(3)
        "Information Regulator",
      ]);
      const processing = sectionText(page, "Personal information we process");
      for (const item of ["Purposes:", "People and information:", "Recipients:", "Planned transfers outside South Africa:", "Security measures:"]) expect(processing).toContain(item);
      expect(sectionText(page, "Availability of this manual")).toContain("www.daskasas.co.za/policies/paia");
      expect(sectionText(page, "Information Regulator")).toContain("Woodmead North Office Park");
      expect(textOf(page)).not.toMatch(/JD House|Stiemens/);
    }
    const draft = sectionText(policyPage(null, "paia"), "Contact details of the head of DasKasas");
    for (const placeholder of [POLICY_PLACEHOLDERS.informationOfficer, POLICY_PLACEHOLDERS.postalAddress, POLICY_PLACEHOLDERS.fax, POLICY_PLACEHOLDERS.informationOfficerEmail]) expect(draft).toContain(placeholder);
    expect(draft).toContain(SHOWROOM.address);
  });
});
