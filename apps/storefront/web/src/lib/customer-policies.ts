import { formatZar } from "./order-money";

export type CustomerPolicyDocument = {
  legal_name: string;
  trading_name: string;
  contact_address: string;
  support_mailbox: string;
  phone: string;
  company_registration_number: string;
  vat_registered: boolean;
  vat_number: string;
  delivery: string;
  collection_location: string;
  collection_instructions: string;
  gauteng_zones: { name: string; rate_zar_incl_vat: string }[];
  terms: string;
  refund_policy: string;
  return_policy: string;
  privacy: string;
  data_collected: string;
  processors: string;
  retention: string;
  information_officer_name: string;
  information_officer_responsibilities: string;
  paia_baseline: string;
  collector_skin: string;
  distinguishes_standard_made_to_order_from_bespoke: true;
};

export type PolicySection = "support" | "contact" | "delivery" | "returns" | "refunds" | "terms" | "privacy";

export type PolicyBlock =
  | { type: "notice"; text: string }
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string };

export type PolicyLink = { href: string; label: string };

export type PolicyView = {
  title: string;
  published: boolean;
  blocks: PolicyBlock[];
  links: PolicyLink[];
};

export const POLICY_REVIEW_NOTICE =
  "Draft for owner and legal review before go-live. Lines in square brackets are missing business details, not Vellano facts.";

export function policyPlaceholder(detail: string): string {
  return `[PLACEHOLDER: ${detail} — to be supplied by Vellano]`;
}

export const POLICY_PLACEHOLDERS = {
  legalName: policyPlaceholder("legal name"),
  tradingName: policyPlaceholder("trading name"),
  registration: policyPlaceholder("company registration number"),
  vat: policyPlaceholder("VAT number, or confirmation that Vellano is not VAT registered"),
  email: policyPlaceholder("support email"),
  phone: policyPlaceholder("phone number"),
  address: policyPlaceholder("physical address"),
  delivery: policyPlaceholder("delivery areas, lead times, and VAT-inclusive ZAR shipping rates"),
  collectionLocation: policyPlaceholder("collection location"),
  collectionInstructions: policyPlaceholder("collection instructions"),
  informationOfficer: policyPlaceholder("Information Officer name"),
  informationOfficerDuties: policyPlaceholder("Information Officer responsibilities"),
  paia: policyPlaceholder("where the PAIA manual is published and how to submit a request"),
} as const;

const TITLES: Record<PolicySection, string> = {
  support: "Support",
  contact: "Contact",
  delivery: "Delivery and collection",
  returns: "Return policy",
  refunds: "Refund policy",
  terms: "Terms and conditions",
  privacy: "Privacy policy",
};

const LINKS: Record<PolicySection, PolicyLink[]> = {
  support: [
    { href: "/contact", label: "Contact" },
    { href: "/policies/returns", label: "Returns" },
    { href: "/policies/refunds", label: "Refunds" },
  ],
  contact: [
    { href: "/policies/privacy", label: "Privacy" },
    { href: "/policies/returns", label: "Returns" },
    { href: "/policies/refunds", label: "Refunds" },
  ],
  delivery: [
    { href: "/policies/returns", label: "Returns" },
    { href: "/policies/refunds", label: "Refunds" },
    { href: "/contact", label: "Contact" },
  ],
  returns: [
    { href: "/policies/refunds", label: "Refunds" },
    { href: "/policies/terms", label: "Terms" },
    { href: "/contact", label: "Contact" },
  ],
  refunds: [
    { href: "/policies/returns", label: "Returns" },
    { href: "/policies/terms", label: "Terms" },
    { href: "/contact", label: "Contact" },
  ],
  terms: [
    { href: "/policies/returns", label: "Return policy" },
    { href: "/policies/refunds", label: "Refund policy" },
    { href: "/policies/delivery", label: "Delivery" },
    { href: "/policies/privacy", label: "Privacy" },
    { href: "/contact", label: "Contact" },
  ],
  privacy: [
    { href: "/contact", label: "Contact" },
    { href: "/policies/terms", label: "Terms" },
  ],
};

export function currentCustomerPolicies(): CustomerPolicyDocument | null {
  // The owner launch pack is not in this repository. Identity, contact, delivery, and the Information Officer stay unmarked until that pack is reviewed.
  return null;
}

function notice(): PolicyBlock {
  return { type: "notice", text: POLICY_REVIEW_NOTICE };
}

function heading(text: string): PolicyBlock {
  return { type: "heading", text };
}

function paragraph(text: string): PolicyBlock {
  return { type: "paragraph", text };
}

function view(section: PolicySection, published: boolean, blocks: PolicyBlock[]): PolicyView {
  return { title: TITLES[section], published, blocks, links: LINKS[section] };
}

function vatLine(document: CustomerPolicyDocument): string {
  return document.vat_registered ? document.vat_number : "Not VAT registered";
}

function zoneLines(document: CustomerPolicyDocument): string[] {
  return document.gauteng_zones.map((zone) => `${zone.name}: ${formatZar(zone.rate_zar_incl_vat)} incl. VAT`);
}

function contactBlocks(document: CustomerPolicyDocument | null): PolicyBlock[] {
  if (!document) {
    return [
      notice(),
      heading("Email"),
      paragraph(POLICY_PLACEHOLDERS.email),
      heading("Phone"),
      paragraph(POLICY_PLACEHOLDERS.phone),
      heading("Physical address"),
      paragraph(POLICY_PLACEHOLDERS.address),
      heading("Company"),
      paragraph(`${POLICY_PLACEHOLDERS.legalName}, trading as ${POLICY_PLACEHOLDERS.tradingName}.`),
      paragraph(`Registration number: ${POLICY_PLACEHOLDERS.registration}.`),
      paragraph(`VAT: ${POLICY_PLACEHOLDERS.vat}.`),
    ];
  }
  return [
    heading("Email"),
    paragraph(document.support_mailbox),
    heading("Phone"),
    paragraph(document.phone),
    heading("Physical address"),
    paragraph(document.contact_address),
    heading("Company"),
    paragraph(`${document.legal_name}, trading as ${document.trading_name}.`),
    paragraph(`Registration number: ${document.company_registration_number}.`),
    paragraph(`VAT: ${vatLine(document)}.`),
  ];
}

function deliveryBlocks(document: CustomerPolicyDocument | null): PolicyBlock[] {
  if (!document) {
    return [
      notice(),
      heading("Delivery"),
      paragraph("Delivery charges, once the owner sets them, are shown in South African Rand (ZAR) and include VAT. They are confirmed in the order total before payment."),
      paragraph(POLICY_PLACEHOLDERS.delivery),
      heading("Collection"),
      paragraph(POLICY_PLACEHOLDERS.collectionLocation),
      paragraph(POLICY_PLACEHOLDERS.collectionInstructions),
    ];
  }
  return [
    heading("Delivery"),
    paragraph(document.delivery),
    ...zoneLines(document).map(paragraph),
    heading("Collection"),
    paragraph(document.collection_location),
    paragraph(document.collection_instructions),
  ];
}

function returnBlocks(document: CustomerPolicyDocument | null): PolicyBlock[] {
  if (document) {
    return [heading("Return policy"), paragraph(document.return_policy)];
  }
  return [
    notice(),
    heading("How to return an item"),
    paragraph("To return a piece, contact Vellano with your order number and say whether you have changed your mind or whether the piece is faulty, damaged, wrong, or not as described. Do not send furniture or decor back until a collection or a drop-off has been agreed. Vellano arranges the return and aims to collect the piece, or to confirm a drop-off at the collection point, within 3 to 10 working days after the request is accepted. Working days are Monday to Friday, excluding South African public holidays."),
    heading("Change of mind"),
    paragraph("You may return an eligible piece because you have changed your mind within 30 days after the day it is delivered to you or the day you collect it. The piece must be unused and in the condition in which it arrived, in its original packaging where it had packaging. Labels and tags must still be on it. Include the invoice or delivery note, the care instructions, and any accessories that came with it and have not been used. If the piece was a gift, the delivery note is still required. A return is refused if a tag has been removed, the piece has been taken apart, it has been built in or permanently installed, or it has been fixed to the building or to another item."),
    heading("Who pays for the return"),
    paragraph("If the return is a change of mind, or the piece is not faulty, and Vellano collects it, a collection fee is charged. That fee is quoted when the collection is booked, before you decide to go ahead. If you bring an eligible piece to the collection point yourself, that collection fee is not charged. On a change of mind the price of the piece is refunded and the delivery charge from the original order is not."),
    heading("What cannot be returned for a change of mind"),
    paragraph("A bespoke commission cannot be returned because you changed your mind. The same applies to a piece that was personalised, resized, engraved, altered, or made to a measurement, fabric, or finish chosen for your order. A standard made-to-order piece is a catalogue piece with a lead time. It is not a bespoke commission. Once it has been delivered or collected, you may return it within the same 30 days, on the same conditions as a stocked piece. An opened consumable that cannot be resold for hygiene reasons, such as a candle that has been burned or a toiletry that has been opened, also cannot be returned for a change of mind."),
    heading("Faulty, wrong, or not as described"),
    paragraph("If the wrong piece arrives, a piece does not match the description on its product page, or parts are missing, leave the labels and packaging as they are and say so straight away. Vellano collects it at no charge and refunds what you paid for that piece, including its delivery charge."),
    paragraph("If a piece is faulty, or it is not of the quality the Consumer Protection Act 68 of 2008 requires, contact Vellano. For furniture you may raise that claim for 12 months from the date of purchase. For other home and decor items you may raise it for 6 months from the date of purchase, unless the product page states a longer warranty. The piece must have been used only in an ordinary home, and only as the care instructions describe. An assessment fee may be required before an inspection. The fee is quoted first. If a fault or a quality problem is confirmed, the assessment fee is refunded, and you choose a repair, a replacement, or a refund of the price you paid."),
    paragraph("Natural markings, small cracks, and live edges in leather or solid wood are part of the material. They are not faults. A problem is not treated as a fault, and an assessment fee is not refunded, where the piece was used, loaded, or cared for against its instructions; where damp, water, or direct sun has marked or faded it; where a piece that is not outdoor furniture was used outside; where it stood against a fireplace, heater, or braai; or where the damage comes from the setting, including coastal air and extreme humidity. The ordinary guarantee also does not apply if the piece is used in a business or industrial setting."),
    paragraph("Nothing in this policy takes away a right you have under the Consumer Protection Act. The 30-day change-of-mind period is longer than the seven-day cooling-off period that the Electronic Communications and Transactions Act 25 of 2002 gives for certain electronic transactions."),
  ];
}

function refundBlocks(document: CustomerPolicyDocument | null): PolicyBlock[] {
  if (document) {
    return [heading("Refund policy"), paragraph(document.refund_policy)];
  }
  return [
    notice(),
    heading("How to request a refund"),
    paragraph("Ask for a refund through the Contact page and include your order number. A refund is available when a return has been accepted, when a fault has been confirmed, or when Vellano cancels the order. A change-of-mind refund follows a return made within 30 days of delivery or collection. A paid order is not cancelled merely because you have changed your mind while the piece is still with you. The piece has to come back under the return policy first, unless Vellano is the one cancelling."),
    paragraph("If Vellano cancels, for example because the piece is no longer available or a price was shown in error, the full amount you paid is refunded. Vellano does not charge a cancellation fee for a cancellation it makes."),
    heading("How a refund is paid, and when"),
    paragraph("The refund goes back to the payment method you used. Where you paid by card, that return is made through Peach Payments. It starts only after the piece is back and the return has been checked, except where Vellano cancels before delivery. It can take up to 10 working days after the piece is received for the refund to show. Your bank may take longer. Working days are Monday to Friday, excluding South African public holidays."),
    heading("Fees and penalties"),
    paragraph("On a change of mind the price of the piece is refunded and the original delivery charge is kept. If Vellano collected the piece, the collection fee quoted when the return was booked is charged and is not refunded. On a confirmed fault, a wrong piece, or a piece that does not match its description, the price and the delivery charge for that piece are refunded, no collection fee is charged, and any assessment fee you paid is refunded."),
    paragraph("If delivery cannot be completed after three attempts because nobody is available to receive the piece or access is not possible, Vellano may cancel the order, keep the failed-delivery cost it incurred, and refund the balance."),
    paragraph("If you do not have the invoice or the delivery note, including where the piece was a gift and that note is missing, a money refund is not paid. Another piece of the same price may be offered. The difference is not paid if you choose a piece that costs less."),
    heading("Made to order and bespoke"),
    paragraph("A standard made-to-order piece is refunded on the same basis as a stocked piece after it has been delivered or collected and returned under the return policy. A bespoke commission is not refunded for a change of mind. If it is faulty, it is repaired, replaced, or refunded under the furniture rules in the return policy."),
    paragraph("These rules do not reduce your rights under the Consumer Protection Act 68 of 2008."),
  ];
}

function termsBlocks(document: CustomerPolicyDocument | null): PolicyBlock[] {
  const identity = document
    ? `${document.legal_name}, trading as ${document.trading_name}. Registration number: ${document.company_registration_number}. VAT: ${vatLine(document)}.`
    : `${POLICY_PLACEHOLDERS.legalName}, trading as ${POLICY_PLACEHOLDERS.tradingName}. Registration number: ${POLICY_PLACEHOLDERS.registration}. VAT: ${POLICY_PLACEHOLDERS.vat}.`;
  const contact = document
    ? `${document.support_mailbox}. ${document.phone}. ${document.contact_address}.`
    : `${POLICY_PLACEHOLDERS.email}. ${POLICY_PLACEHOLDERS.phone}. ${POLICY_PLACEHOLDERS.address}.`;
  if (document) {
    return [
      heading("Who these terms cover"),
      paragraph(`These terms cover use of the Vellano storefront and purchases of home and decor pieces from ${identity}`),
      heading("Prices"),
      paragraph("Every customer-facing price is shown in South African Rand (ZAR). Product prices include VAT where VAT applies. The amount you pay is the ZAR total shown at checkout before you pay."),
      heading("Terms"),
      paragraph(document.terms),
      heading("Contact"),
      paragraph(contact),
    ];
  }
  return [
    notice(),
    heading("Who these terms cover"),
    paragraph(`These terms cover use of the Vellano storefront and purchases of home and decor pieces from ${identity}`),
    heading("Prices"),
    paragraph("Every customer-facing price is shown in South African Rand (ZAR). Product prices include VAT where VAT applies. The amount you pay is the ZAR total shown at checkout before you pay."),
    heading("Orders"),
    paragraph("Adding a piece to your bag does not buy it. Vellano accepts the order by delivering the pieces or by making them ready for collection. Until then, Vellano may cancel if a piece is unavailable or a price was shown in error, and will refund the full amount already paid with no cancellation fee."),
    heading("Returns and refunds"),
    paragraph("You may return an eligible piece because you have changed your mind within 30 days after delivery or collection. It must be unused, in its original condition, with labels and tags still attached, and with the invoice or delivery note, care instructions, and unused accessories. A gift still needs the delivery note. A return is refused if a tag has been removed, the piece has been taken apart, permanently installed, or fixed to the building or to another item."),
    paragraph("A change-of-mind return that Vellano collects incurs a collection fee, quoted before you confirm the collection. Bringing an eligible piece to the collection point does not incur that fee. The refund is the price of the piece. The original delivery charge is not refunded. The refund goes back to the payment method you used, through Peach Payments where you paid by card, and can take up to 10 working days after the piece is received to show."),
    paragraph("A bespoke commission, and any piece personalised, resized, engraved, altered, or made to a measurement, fabric, or finish chosen for your order, cannot be returned or refunded for a change of mind. A standard made-to-order piece is a catalogue piece with a lead time, not a bespoke commission, and may be returned within the same 30 days once it has been delivered or collected. A paid order is not cancelled for a change of mind while the piece is still with you."),
    paragraph("A wrong piece, a piece that does not match its description, or a piece with missing parts is collected at no charge, and the price and delivery charge for that piece are refunded. A faulty piece may be claimed for 6 months from purchase, or 12 months for furniture, if it was used only at home and cared for as instructed. You choose a repair, a replacement, or a refund of the price after a fault is confirmed. An assessment fee, if quoted and charged, is refunded when the fault is confirmed. Natural markings in leather or solid wood are not faults. Nothing here limits the Consumer Protection Act 68 of 2008. The 30-day period is longer than the seven-day cooling-off period in the Electronic Communications and Transactions Act 25 of 2002."),
    heading("Delivery and collection"),
    paragraph("Delivery charges are shown in ZAR, include VAT, and are confirmed in the order total before payment."),
    paragraph(POLICY_PLACEHOLDERS.delivery),
    paragraph(POLICY_PLACEHOLDERS.collectionLocation),
    paragraph(POLICY_PLACEHOLDERS.collectionInstructions),
    heading("Care, materials, and liability"),
    paragraph("Follow the care instructions supplied with the piece. Vellano is not liable for damage caused by use that ignores those instructions, or for the natural variation of wood and leather. This does not limit liability that South African law does not allow a supplier to limit."),
    heading("Contact"),
    paragraph(contact),
  ];
}

function privacyBlocks(document: CustomerPolicyDocument | null): PolicyBlock[] {
  if (document) {
    return [
      heading("Privacy"),
      paragraph(document.privacy),
      heading("Personal information collected"),
      paragraph(document.data_collected),
      heading("Operators and processors"),
      paragraph(document.processors),
      heading("Retention"),
      paragraph(document.retention),
      heading("Information Officer"),
      paragraph(document.information_officer_name),
      paragraph(document.information_officer_responsibilities),
      heading("PAIA"),
      paragraph(document.paia_baseline),
    ];
  }
  return [
    notice(),
    heading("Responsible party"),
    paragraph(`The responsible party under the Protection of Personal Information Act 4 of 2013 (POPIA) is ${POLICY_PLACEHOLDERS.legalName}, trading as ${POLICY_PLACEHOLDERS.tradingName}. Registration number: ${POLICY_PLACEHOLDERS.registration}. VAT: ${POLICY_PLACEHOLDERS.vat}.`),
    heading("Information Officer"),
    paragraph(`Name: ${POLICY_PLACEHOLDERS.informationOfficer}.`),
    paragraph(`Responsibilities: ${POLICY_PLACEHOLDERS.informationOfficerDuties}.`),
    paragraph(`Privacy requests can be sent to ${POLICY_PLACEHOLDERS.email}, by phone at ${POLICY_PLACEHOLDERS.phone}, or by post to ${POLICY_PLACEHOLDERS.address}.`),
    heading("Personal information collected"),
    paragraph("To sell and deliver a piece, the storefront collects the name, email address, phone number, and delivery or collection details you enter, the contents of the order, and a payment reference. Full card numbers are handled by the payment provider and are not stored as part of the catalogue. Account sign-in collects the identity details the sign-in service needs. Optional analytics stay off until you accept them, and they are not used to send search text, personal details, or payment data."),
    heading("Operators and processors"),
    paragraph("The storefront is built to use these operators: Clerk for account sign-in, PostHog for optional analytics, Peach for card payments, SendGrid for transactional email, and Railway for hosting. Each operator may process the personal information needed for that role. This list is the set the software is built for and should be confirmed before go-live."),
    heading("Retention"),
    paragraph("Order, tax, and payment records are kept for as long as South African tax and accounting law requires and for as long as a return, refund, or dispute about that order is open. Account details are kept while the account is open and then for as long as those legal duties remain. Optional analytics are not collected unless you accept them, and they are not kept for a purpose that acceptance did not cover."),
    heading("PAIA"),
    paragraph(POLICY_PLACEHOLDERS.paia),
    heading("Your rights"),
    paragraph("You may ask what personal information is held, ask for a correction, object to processing that POPIA allows you to object to, and lodge a complaint with the Information Regulator. Those requests go to the Information Officer once that person is named."),
  ];
}

export function policyPage(document: CustomerPolicyDocument | null, section: PolicySection): PolicyView {
  if (section === "support" || section === "contact") return view(section, document !== null, contactBlocks(document));
  if (section === "delivery") return view(section, document !== null, deliveryBlocks(document));
  if (section === "returns") return view(section, document !== null, returnBlocks(document));
  if (section === "refunds") return view(section, document !== null, refundBlocks(document));
  if (section === "terms") return view(section, document !== null, termsBlocks(document));
  return view(section, document !== null, privacyBlocks(document));
}

export function contactDetails(document: CustomerPolicyDocument | null): { email: string; phone: string; address: string } {
  if (!document) {
    return {
      email: POLICY_PLACEHOLDERS.email,
      phone: POLICY_PLACEHOLDERS.phone,
      address: POLICY_PLACEHOLDERS.address,
    };
  }
  return {
    email: document.support_mailbox,
    phone: document.phone,
    address: document.contact_address,
  };
}
