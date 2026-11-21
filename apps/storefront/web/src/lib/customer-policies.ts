import { formatZar } from "./order-money";
import { SHOWROOM } from "./showroom";

// Statutory sources, checked against the Government Gazette texts (CPA: GG 32186; ECTA: GG 23708) on 21 Nov 2026.
// Research notes (cited below by file name): apps/storefront/docs/research-made-to-order-law.md and apps/storefront/docs/research-popia-paia-ecta.md.
// The terms, returns, refunds and delivery wording below is DasKasas's own; the owner document supplies only business facts.
export type CustomerPolicyDocument = {
  legal_name: string;
  trading_name: string;
  // ECTA s43(1)(a): legal status, with the place of registration that s43(1)(f) asks for.
  legal_status: string;
  // ECTA s43(1)(f): names of the office bearers (directors).
  office_bearers: string[];
  // ECTA s43(1)(g): where DasKasas accepts legal service of documents.
  legal_service_address: string;
  // ECTA s43(1)(d), (e), (o): self-regulatory bodies, codes of conduct and dispute-resolution codes, or a statement that there are none.
  codes_of_conduct: string;
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
  // POPIA s55 and PAIA s1 "head": the CEO or managing director, or the person they authorise in writing. Must match the Regulator registration.
  information_officer_name: string;
  information_officer_email: string;
  // PAIA s51(1)(a)(i): postal address and fax number of the head of the body; fax_number may say there is none.
  postal_address: string;
  fax_number: string;
  collector_skin: string;
  distinguishes_standard_made_to_order_from_bespoke: true;
};

export type PolicySection = "delivery" | "returns" | "refunds" | "terms" | "privacy" | "paia";

export type PolicyBlock =
  | { type: "notice"; text: string }
  | { type: "heading"; text: string; id?: string }
  | { type: "paragraph"; text: string };

export type PolicyLink = { href: string; label: string };

export type PolicyView = {
  title: string;
  published: boolean;
  blocks: PolicyBlock[];
  links: PolicyLink[];
};

export const POLICY_DRAFT_NOTICE = "Draft for owner and legal review before go-live.";
export const POLICY_REVIEW_NOTICE =
  `${POLICY_DRAFT_NOTICE} Lines in square brackets are missing business details, not DasKasas facts.`;

export function policyPlaceholder(detail: string): string {
  return `[PLACEHOLDER: ${detail} — to be supplied by DasKasas]`;
}

export const POLICY_PLACEHOLDERS = {
  legalName: policyPlaceholder("legal name"),
  tradingName: policyPlaceholder("trading name"),
  legalStatus: policyPlaceholder("legal status and place of registration"),
  officeBearers: policyPlaceholder("names of the directors (office bearers)"),
  legalServiceAddress: policyPlaceholder("physical address for legal service of documents"),
  codesOfConduct: policyPlaceholder("industry bodies, codes of conduct or dispute-resolution codes DasKasas subscribes to, or confirmation that there are none"),
  registration: policyPlaceholder("company registration number"),
  vat: policyPlaceholder("VAT number, or confirmation that DasKasas is not VAT registered"),
  delivery: policyPlaceholder("delivery areas, lead times, and VAT-inclusive ZAR shipping rates"),
  informationOfficer: policyPlaceholder("Information Officer name"),
  informationOfficerEmail: policyPlaceholder("Information Officer email"),
  postalAddress: policyPlaceholder("postal address"),
  fax: policyPlaceholder("fax number, or confirmation that there is none"),
} as const;

const TITLES: Record<PolicySection, string> = {
  delivery: "Delivery and collection",
  returns: "Return policy",
  refunds: "Refund policy",
  terms: "Terms and conditions",
  privacy: "Privacy policy",
  paia: "PAIA manual",
};

const LINKS: Record<PolicySection, PolicyLink[]> = {
  delivery: [
    { href: "/policies/returns", label: "Returns" },
    { href: "/policies/refunds", label: "Refunds" },
    { href: "/help#contact", label: "Contact" },
  ],
  returns: [
    { href: "/policies/refunds", label: "Refunds" },
    { href: "/policies/terms", label: "Terms" },
    { href: "/help#contact", label: "Contact" },
  ],
  refunds: [
    { href: "/policies/returns", label: "Returns" },
    { href: "/policies/terms", label: "Terms" },
    { href: "/help#contact", label: "Contact" },
  ],
  terms: [
    { href: "/policies/returns", label: "Return policy" },
    { href: "/policies/refunds", label: "Refund policy" },
    { href: "/policies/delivery", label: "Delivery" },
    { href: "/policies/privacy", label: "Privacy" },
    { href: "/help#contact", label: "Contact" },
  ],
  privacy: [
    { href: "/policies/paia", label: "PAIA manual" },
    { href: "/help#contact", label: "Contact" },
    { href: "/policies/terms", label: "Terms" },
  ],
  paia: [
    { href: "/policies/privacy", label: "Privacy" },
    { href: "/help#contact", label: "Contact" },
  ],
};

export function currentCustomerPolicies(): CustomerPolicyDocument | null {
  // The owner launch pack is not in this repository. Identity, contact, delivery, and the Information Officer stay unmarked until that pack is reviewed.
  return null;
}

function notice(): PolicyBlock {
  return { type: "notice", text: POLICY_REVIEW_NOTICE };
}

function heading(text: string, id?: string): PolicyBlock {
  return { type: "heading", text, id };
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

// Public address the storefront is served from (apps/storefront/web/project.json NEXT_PUBLIC_BASE_URL).
const WEBSITE = "www.daskasas.co.za";

const SHOWROOM_HOURS = SHOWROOM.hours.map((row) => `${row.days} ${row.time}`).join(", ");

// Identity facts stay placeholders until the owner document lands (F0rge/f0rge#1006).
function businessFacts(document: CustomerPolicyDocument | null) {
  if (!document) {
    return {
      legalName: POLICY_PLACEHOLDERS.legalName,
      tradingName: POLICY_PLACEHOLDERS.tradingName,
      legalStatus: POLICY_PLACEHOLDERS.legalStatus,
      registration: POLICY_PLACEHOLDERS.registration,
      officeBearers: POLICY_PLACEHOLDERS.officeBearers,
      legalServiceAddress: POLICY_PLACEHOLDERS.legalServiceAddress,
      vat: POLICY_PLACEHOLDERS.vat,
      codesOfConduct: POLICY_PLACEHOLDERS.codesOfConduct,
    };
  }
  return {
    legalName: document.legal_name,
    tradingName: document.trading_name,
    legalStatus: document.legal_status,
    registration: document.company_registration_number,
    officeBearers: document.office_bearers.join(", "),
    legalServiceAddress: document.legal_service_address,
    vat: vatLine(document),
    codesOfConduct: document.codes_of_conduct,
  };
}

// The showroom's address, phones and email are public facts Leo confirmed (lib/showroom.ts), so they stand in until the owner document names a support address.
function contactFacts(document: CustomerPolicyDocument | null): { address: string; phone: string; email: string } {
  if (document) return { address: document.contact_address, phone: document.phone, email: document.support_mailbox };
  return { address: SHOWROOM.address, phone: SHOWROOM.phones.map((phone) => phone.number).join(" or "), email: SHOWROOM.email };
}

function collectionLines(document: CustomerPolicyDocument | null): string[] {
  if (document) return [document.collection_location, document.collection_instructions];
  return [
    `You can collect free of charge from our showroom at ${SHOWROOM.address}. ${SHOWROOM.note}`,
    `The showroom is open ${SHOWROOM_HOURS}. We contact you when your order is ready to collect.`,
  ];
}

// CPA s49(1): terms that limit our liability or ask the customer to accept a fact. One source for the terms page and checkout.
// None is an unusual or serious-injury risk (s49(2)), so no separate signed or ticked assent is needed.
export const IMPORTANT_TERMS_PURPOSE = "They limit what we are responsible for, or ask you to accept certain facts.";
export const IMPORTANT_TERMS = [
  "Wood, leather and natural fabrics vary: grain, knots, small cracks, live edges and colour differences are part of the material, not faults.",
  "Colours look different on screens, so visit the showroom to see a piece in person.",
  "We are not responsible for damage caused by misuse, an accident, or care that goes against the care instructions supplied with a piece.",
  "If we cannot deliver after three attempts because nobody is there or we cannot get access, we may cancel the order, keep the cost of the failed deliveries and refund the rest.",
  "If we collect a change-of-mind return, you pay the collection fee we quote when you book it.",
] as const;

// ECTA s44(1)(a), (2), (3): seven days from receipt, only the direct cost of return, full refund within 30 days.
// ECTA s42(2)(f): no cooling-off for goods made to the consumer's specifications, clearly personalised, not returnable by nature, or likely to deteriorate.
// Treating a chosen measurement, fabric or finish as "made to your specifications" is DasKasas's reading; no SA decision on s42(2)(f) exists (research-made-to-order-law.md §6).
const COOLING_OFF = [
  "If you buy online, you may cancel without giving a reason within 7 days after you receive the goods. Tell us by email or phone.",
  "We refund everything you paid, including the delivery charge, within 30 days after you cancel. The only cost you may have to pay is the direct cost of returning the goods.",
  "This 7-day right does not apply to goods made to your specifications or clearly personalised. It also does not apply to goods that by their nature cannot be returned, or that are likely to deteriorate quickly. We treat a bespoke commission, and a piece made to a measurement, fabric or finish you chose for your order, as made to your specifications.",
];

// One-line returns summaries for Help and the home FAQ; the returns and refunds pages above and below hold the full wording.
export const RETURNS_SUMMARY = {
  coolingOff: "If you buy online, you may cancel within 7 days after you receive the goods and get back everything you paid, including the delivery charge (you may have to pay only the direct cost of returning them); this does not apply to goods made to your specifications or clearly personalised, or that by their nature cannot be returned or deteriorate quickly.",
  changeOfMind: "Our own policy: if you change your mind, you may return a piece within 30 days after delivery or collection, unused and in the condition it arrived in, with its labels and tags, original packaging and the invoice or delivery note.",
  howToReturn: "Contact us with your order number before sending anything back, and we agree a collection or a drop-off at the showroom.",
  changeOfMindCosts: "For a change-of-mind return we refund the price of the piece and keep the original delivery charge. If we collect it, you pay the collection fee we quote when you book; there is no fee if you bring it to the showroom.",
  notReturnable: "Bespoke commissions, and pieces personalised or made to a measurement, fabric or finish chosen for your order, cannot be returned for a change of mind.",
} as const;

// CPA s19(5) and s18(3): the consumer may examine goods on delivery and reject goods that do not match the order or description.
const WRONG_PIECE = "If the wrong piece arrives, a piece does not match the description on its product page, or parts are missing, leave the labels and packaging as they are and tell us straight away. We collect it at no charge and refund what you paid for that piece, including its delivery charge.";

// CPA s55(2): good quality, working order, free of defects, durable. CPA s56(2): return within six months after DELIVERY,
// without penalty and at the supplier's risk and expense; the consumer chooses repair, replacement or refund. s56(3): failed repair
// within three months means replacement or refund. s55 and s56 do not exclude special-order goods. s56(1): no warranty where goods
// were altered contrary to instructions. No assessment fee: s56(2) says "without penalty" (research-made-to-order-law.md §5).
const FAULTS = [
  "Every piece must be of good quality, in good working order and free of defects. It must also last for a reasonable time.",
  "If a piece is faulty, you may return it to us within six months after delivery. You pay no fee, and we carry the risk and cost of the return. You choose whether we repair it, replace it or refund the price you paid.",
  "If we repair a piece and the fault is not fixed within three months, or a new fault appears in that time, we replace it or refund the price you paid.",
  "We never charge you to inspect a fault.",
  "These rights cover every piece, including made-to-order pieces and bespoke commissions.",
  "Natural markings in wood, leather and natural fabric are not faults. Nor is damage caused by misuse, an accident, or care that goes against the care instructions.",
];

const YOUR_RIGHTS_STAY = "Nothing in this policy takes away a right you have under the Consumer Protection Act 68 of 2008 or the Electronic Communications and Transactions Act 25 of 2002.";

function deliveryBlocks(document: CustomerPolicyDocument | null): PolicyBlock[] {
  const areas = document ? [paragraph(document.delivery), ...zoneLines(document).map(paragraph)] : [paragraph(POLICY_PLACEHOLDERS.delivery)];
  const blocks: PolicyBlock[] = [
    heading("Where we deliver"),
    paragraph("We deliver in selected Gauteng areas. Delivery charges are shown in South African rand (ZAR) and include VAT. They are confirmed in your order total before you pay."),
    ...areas,
    // ECTA s46(1)-(2) for online orders; DasKasas applies the same promise to showroom orders. ECTA s43(1)(l): delivery time on the site.
    heading("When we deliver"),
    paragraph("A piece in stock is delivered within 30 days after we receive your order, unless we agree another date with you."),
    paragraph("A made-to-order piece shows its lead time on its product page. That lead time is the delivery period we agree with you."),
    paragraph("If we miss the agreed delivery period, you may cancel the order by giving us 7 days' written notice, for example by email. We then refund the full amount you paid."),
    // CPA s19(5): examine on delivery. CPA s19(2)(c): goods stay at the supplier's risk until delivery is accepted.
    heading("When it arrives"),
    paragraph("Check each piece before you accept it. You may refuse a piece that is damaged or not what you ordered. A piece stays at our risk until you accept delivery or collect it."),
    paragraph("If we cannot deliver after three attempts because nobody is there to receive the piece, or we cannot get access, we may cancel the order. We keep the cost of the failed deliveries and refund the rest."),
    heading("Collection"),
    ...collectionLines(document).map(paragraph),
  ];
  return document ? blocks : [notice(), ...blocks];
}

function returnBlocks(document: CustomerPolicyDocument | null): PolicyBlock[] {
  const blocks: PolicyBlock[] = [
    heading("How to return a piece"),
    paragraph("Contact us with your order number. Say whether you have changed your mind, or whether the piece is faulty, damaged, wrong or not as described. Do not send a piece back until we have agreed a collection or a drop-off. We aim to collect it, or to confirm a drop-off at the showroom, within 3 to 10 working days after we accept the request. Working days are Monday to Friday, excluding South African public holidays."),
    heading("Online orders: 7 days to cancel"),
    ...COOLING_OFF.map(paragraph),
    paragraph("The change-of-mind conditions below do not reduce this right."),
    // DasKasas's own policy: the CPA has no change-of-mind return right (s20 lists only specific grounds).
    heading("Change of mind"),
    paragraph("This is our own policy. It goes further than the law requires, and covers online and showroom purchases."),
    paragraph("You may return a piece because you have changed your mind within 30 days after the day it is delivered or collected. It must be unused and in the condition it arrived in, in its original packaging where it had packaging. Labels and tags must still be on it. Include the invoice or delivery note, the care instructions, and any unused accessories that came with it. A gift still needs the delivery note. We refuse a return if a tag has been removed, or if the piece has been taken apart, built in, permanently installed, or fixed to the building or to another item."),
    heading("Who pays for a change-of-mind return"),
    paragraph("If we collect the piece, you pay a collection fee. We quote it when you book the collection, before you decide to go ahead. If you bring the piece to the showroom yourself, there is no collection fee. We refund the price of the piece. We do not refund the original delivery charge."),
    // CPA s1: "special-order goods" are procured, created or altered specifically to satisfy the consumer's requirements.
    heading("What cannot be returned for a change of mind"),
    paragraph("A bespoke commission cannot be returned because you changed your mind. Nor can a piece that was personalised, resized, engraved or altered, or made to a measurement, fabric or finish chosen for your order. These are special-order goods: we buy or make them only for you."),
    paragraph("A standard made-to-order piece is different. It is a catalogue piece with a lead time, made in its listed form. Once it is delivered or collected, you may return it within the same 30 days, on the same conditions as a piece in stock."),
    paragraph("An opened consumable that cannot be resold for hygiene reasons, such as a burned candle or an opened toiletry, also cannot be returned for a change of mind."),
    heading("Wrong, damaged or not as described"),
    paragraph(WRONG_PIECE),
    heading("Faulty pieces"),
    ...FAULTS.map(paragraph),
    paragraph(YOUR_RIGHTS_STAY),
  ];
  return document ? blocks : [notice(), ...blocks];
}

function refundBlocks(document: CustomerPolicyDocument | null): PolicyBlock[] {
  const blocks: PolicyBlock[] = [
    heading("When you get a refund"),
    paragraph("Ask for a refund through the Contact page and include your order number. You get a refund when you cancel an online order within the 7-day cooling-off period, when we accept a change-of-mind return, when a piece is faulty, wrong or not as described, or when we cancel the order."),
    paragraph("A change-of-mind refund follows a return made within 30 days after delivery or collection. Outside the 7-day cooling-off period, a delivered piece has to come back under the return policy before we refund it."),
    // ECTA s46(3): unavailable goods are refunded within 30 days of notifying the consumer. ECTA s46(2): cancellation for late delivery.
    paragraph("If we cancel, for example because a piece is unavailable or a price was shown in error, we tell you straight away. We refund the full amount you paid within 30 days. We do not charge a cancellation fee. If you cancel because we missed the agreed delivery period, we also refund the full amount you paid."),
    heading("How a refund is paid, and when"),
    paragraph("The refund goes back to the payment method you used. If you paid by card, Paystack returns it to your card. For a return, the refund starts once the piece is back with us and has been checked. It can take up to 10 working days after we receive the piece for the refund to show. Your bank may take longer. A cooling-off refund is always made within 30 days after you cancel. Working days are Monday to Friday, excluding South African public holidays."),
    // ECTA s44(2)-(3): full refund, only the direct cost of return may be charged. CPA s56(2): faults at the supplier's risk and expense.
    heading("What we refund"),
    paragraph("7-day cooling-off: everything you paid, including the delivery charge. The only cost you may have to pay is the direct cost of returning the goods."),
    paragraph("Change of mind: the price of the piece. We keep the original delivery charge. If we collected the piece, we charge the collection fee quoted when you booked the return."),
    paragraph("Faulty, wrong or not as described: the price and the delivery charge for that piece. There is no collection fee and no inspection fee."),
    paragraph("If we cannot deliver after three attempts because nobody is there to receive the piece, or we cannot get access, we may cancel the order. We keep the cost of the failed deliveries and refund the rest."),
    paragraph("For a change-of-mind return without the invoice or delivery note, including a gift without its delivery note, we do not refund money. We may offer another piece of the same price instead. If you choose a cheaper piece, we do not pay the difference."),
    heading("Made to order and bespoke"),
    paragraph("A standard made-to-order piece is refunded on the same basis as a piece in stock, once it has been delivered or collected and returned under the return policy. A bespoke commission is not refunded for a change of mind. If a bespoke piece is faulty, you choose a repair, a replacement or a refund, as for any other piece."),
    paragraph("These rules do not reduce your rights under the Consumer Protection Act 68 of 2008 or the Electronic Communications and Transactions Act 25 of 2002."),
  ];
  return document ? blocks : [notice(), ...blocks];
}

function termsBlocks(document: CustomerPolicyDocument | null): PolicyBlock[] {
  const business = businessFacts(document);
  const contact = contactFacts(document);
  const blocks: PolicyBlock[] = [
    heading("Who these terms cover"),
    paragraph(`These terms apply when you buy from DasKasas, online at ${WEBSITE} or in our showroom. DasKasas is ${business.legalName}, trading as ${business.tradingName}. "We" and "us" mean DasKasas. "You" means the person buying.`),
    paragraph("Some rights apply only to online orders. We say so where that is the case."),
    // CPA s51(1)(b): a term may not waive a CPA right. ECTA s48: a term excluding Chapter VII rights is void.
    paragraph("Nothing in these terms takes away a right you have under the Consumer Protection Act 68 of 2008 (CPA) or the Electronic Communications and Transactions Act 25 of 2002 (ECTA)."),
    // ECTA s43(1)(a)-(g): name and legal status; physical address and phone; website and email; self-regulatory bodies and codes;
    // registration number, office bearers and place of registration; address for legal service. s43(1)(o): dispute-resolution codes.
    heading("Business information", "business-information"),
    paragraph(`Full name: ${business.legalName}, trading as ${business.tradingName}.`),
    paragraph(`Legal status and place of registration: ${business.legalStatus}.`),
    paragraph(`Registration number: ${business.registration}.`),
    paragraph(`Directors: ${business.officeBearers}.`),
    paragraph(`VAT: ${business.vat}.`),
    paragraph(`Physical address: ${contact.address}.`),
    paragraph(`Address for legal documents: ${business.legalServiceAddress}.`),
    paragraph(`Phone: ${contact.phone}.`),
    paragraph(`Email: ${contact.email}.`),
    paragraph(`Website: ${WEBSITE}.`),
    paragraph(`Industry bodies, codes of conduct and dispute resolution: ${business.codesOfConduct}.`),
    // CPA s49(1), (3)-(4)(a): plain language, conspicuous. Checkout shows the same IMPORTANT_TERMS before payment (s49(4)(b)).
    heading("Important terms", "important-terms"),
    { type: "notice", text: `Please read these points before you pay. ${IMPORTANT_TERMS_PURPOSE} ${IMPORTANT_TERMS.join(" ")} None of these points reduces your rights under the CPA or ECTA.` },
    // ECTA s43(2): review, correct and withdraw before placing the order. s43(1)(m): record of the transaction. s43(1)(k) and CPA s50(2): free access to the terms.
    heading("Ordering"),
    paragraph("Adding a piece to your bag does not buy it."),
    paragraph("Before you pay, checkout shows your pieces, quantities, delivery or collection, any delivery charge and the total. You can go back and change anything, or leave without paying. Your order is placed only when you pay."),
    paragraph("We accept your order when we deliver it or make it ready for collection. Until then, we may cancel it if a piece is unavailable or a price was shown in error. If we cancel, we tell you straight away and refund the full amount you paid within 30 days. We do not charge a cancellation fee."),
    paragraph("After you pay, we email you an order confirmation with a link to your order. Keep it as your record of the order. If you have an account, your orders are listed there too."),
    paragraph(`These terms are always at ${WEBSITE}/policies/terms. You can read, print or save them free of charge.`),
    // ECTA s43(1)(i): full price including transport costs and taxes.
    heading("Prices and VAT"),
    paragraph("Prices are in South African rand (ZAR). Product prices include VAT where VAT applies. Our VAT status is in the business information above."),
    paragraph("Checkout shows any delivery charge, including VAT, before you pay. Collection from the showroom is free."),
    paragraph("You pay the total shown at checkout. We do not change the price after you have paid."),
    // ECTA s43(1)(j): manner of payment. s43(1)(p) and s43(5): payment security procedures and a sufficiently secure payment system.
    heading("Payment"),
    paragraph("You pay online by card. Paystack processes card payments for us."),
    paragraph("You enter your card details on Paystack's secure payment page, not on our site. We never see or store your full card number. Our site and the payment page use encrypted (HTTPS) connections."),
    paragraph("If card payment is not available at checkout, call or email us to arrange your order."),
    // ECTA s43(1)(l), s46(1)-(2); CPA s19(5).
    heading("Delivery and collection"),
    paragraph("We deliver in selected Gauteng areas. The delivery policy lists the areas and charges."),
    paragraph("A piece in stock is delivered within 30 days after we receive your order, unless we agree another date with you. A made-to-order piece shows its lead time on its product page. That lead time is the delivery period we agree with you."),
    paragraph("If we miss the agreed delivery period, you may cancel the order by giving us 7 days' written notice, for example by email. We then refund the full amount you paid."),
    paragraph(collectionLines(document).join(" ")),
    // CPA s19(2)(c): risk stays with the supplier until delivery is accepted.
    heading("Risk and ownership"),
    paragraph("A piece is at our risk until you accept delivery or collect it. Check each piece when it arrives. You may refuse a piece that is damaged or not what you ordered."),
    paragraph("A piece becomes yours once you have paid in full and it has been delivered or collected."),
    // ECTA s43(1)(n), (r): return policy and the s44 rights.
    heading("Cancellations and returns"),
    ...COOLING_OFF.map(paragraph),
    paragraph("Change of mind is our own policy and goes further than the law. It covers online and showroom purchases. You may return a piece in stock or a standard made-to-order piece within 30 days after delivery or collection, unused and in the condition it arrived in. The return policy sets out the conditions and the collection fee."),
    paragraph("A standard made-to-order piece is a catalogue piece, made in its listed form after you order. A bespoke commission is made or altered only for you, which makes it special-order goods under the CPA. A bespoke or personalised piece cannot be returned for a change of mind."),
    paragraph(WRONG_PIECE),
    // ECTA s43(1)(k): guarantees. CPA s55-s56 as cited on FAULTS.
    heading("Faults and guarantees"),
    ...FAULTS.map(paragraph),
    // CPA s51(1)(c)(i): no exclusion for gross negligence. ECTA s43(6): liability for an insecure payment system.
    heading("Liability"),
    paragraph("We do not exclude or limit liability where the law does not allow it. That includes liability for gross negligence."),
    paragraph("We are liable for any damage you suffer because our payment system was not secure enough."),
    paragraph("We are not responsible for damage caused by misuse, an accident, or care that goes against the care instructions. This is one of the important terms above."),
    heading("Privacy"),
    paragraph("Our privacy policy explains what personal information we collect, why we collect it, and how we protect it."),
    heading("Governing law and complaints"),
    paragraph("South African law applies to these terms."),
    paragraph("If something goes wrong, contact us first. You may also complain to the National Consumer Commission."),
    heading("Contact"),
    paragraph(`Email ${contact.email}. Phone ${contact.phone}. Showroom: ${SHOWROOM.address}, open ${SHOWROOM_HOURS}.`),
  ];
  return document ? blocks : [notice(), ...blocks];
}

// POPIA s55 and PAIA s51(1)(a): the Information Officer (head of the body) and how to reach them; placeholders until #1006.
function officerFacts(document: CustomerPolicyDocument | null) {
  if (!document) {
    return {
      name: POLICY_PLACEHOLDERS.informationOfficer,
      email: POLICY_PLACEHOLDERS.informationOfficerEmail,
      postalAddress: POLICY_PLACEHOLDERS.postalAddress,
      fax: POLICY_PLACEHOLDERS.fax,
    };
  }
  return { name: document.information_officer_name, email: document.information_officer_email, postalAddress: document.postal_address, fax: document.fax_number };
}

// POPIA s18(1)(h)(v) and s74; PAIA s77A. Current details from inforegulator.org.za (Contact and Complaints pages, checked 21 Nov 2026).
// The JD House, Stiemens Street, Braamfontein street address on older Regulator documents is stale; the P.O. Box is current.
const INFORMATION_REGULATOR = [
  "Information Regulator (South Africa)",
  "Address: Woodmead North Office Park, 54 Maxwell Drive, Woodmead, Johannesburg, 2191. Post: P.O. Box 31533, Braamfontein, Johannesburg, 2017.",
  "Phone: 010 023 5200. Toll-free: 0800 017 160.",
  "General enquiries: enquiries@inforegulator.org.za. POPIA complaints: POPIAComplaints@inforegulator.org.za, or online through the eServices Portal at eservices.inforegulator.org.za.",
  "Website: inforegulator.org.za.",
];

// POPIA s18(1)(c) and s11(1): each purpose with its lawful basis.
const PURPOSES = [
  "To take, deliver and support your order: we process the order, arrange delivery or collection, send order and delivery emails, and handle returns, refunds and faults. We need the information to carry out our contract with you (POPIA section 11(1)(b)).",
  "To run your account, if you choose to have one: sign-in, saved delivery addresses and your order history. This also carries out our contract with you.",
  "To keep the records the law requires, such as tax and accounting records (section 11(1)(c)).",
  "To keep the shop secure and prevent fraud and misuse. This is our legitimate interest (section 11(1)(f)), and you may object to it.",
  "To learn which pieces and shop filters are useful, only if you accept optional analytics. Your consent is the basis (section 11(1)(a)), and you may withdraw it at any time.",
  "We do not sell your personal information.",
];

// POPIA s18(1)(h)(i) recipients; s18(1)(g) and s72 where each is based. Railway: the DasKasas database runs in its US West (sfo) region (Railway project config, 21 Nov 2026).
// PostHog: the storefront sends only to the EU host (lib/analytics/policy.ts). Vendor DPAs were not reviewed (research-popia-paia-ecta.md §1.4).
const RECIPIENTS = [
  "Paystack processes card payments. It receives your name, email address, the order amount and the card details you enter on its payment page. Paystack is based in Nigeria and also operates in South Africa.",
  "SendGrid (Twilio) sends our order and delivery emails. It receives your name, email address and order details. It is based in the United States.",
  "Clerk runs account sign-in. It receives your email address and sign-in activity. It is based in the United States.",
  "Railway hosts our website, shop system and database, which hold all the information described here. It is based in the United States, and our database runs in its United States (California) region.",
  "PostHog receives analytics events, only if you accept optional analytics. We use PostHog's EU cloud, hosted in the European Union.",
  "Whoever delivers your order receives your name, phone number, delivery address and the pieces to deliver.",
  "We also share information when the law requires it, for example with the South African Revenue Service.",
];

// POPIA s72(1): (a) binding agreement with substantially similar protection, (b) consent, (c) necessary for the contract with the data subject.
const TRANSFERS = [
  "Some of these providers are outside South Africa. POPIA section 72 allows this only on certain grounds. The ground we rely on for each provider is:",
  "Paystack (Nigeria, when a payment is not processed in South Africa) and SendGrid (United States): the transfer is necessary to carry out your purchase (section 72(1)(c)).",
  "Clerk (United States) and Railway (United States): an agreement that binds the provider to protection substantially similar to POPIA, including limits on passing the information on (section 72(1)(a)).",
  "PostHog (European Union): your consent to optional analytics (section 72(1)(b)) and an agreement as above (section 72(1)(a)). PostHog is also bound there by the EU General Data Protection Regulation.",
];

// POPIA s19 (and s20-s22 for operators and breaches); ECTA s43(1)(p) security procedures.
const SAFEGUARDS = [
  "We take reasonable technical and organisational steps to protect your information against loss, damage and unauthorised access.",
  "Our website, the payment page and our providers use encrypted (HTTPS) connections. You enter card details on Paystack's secure payment page, so we never see or store your full card number.",
  "Only people who need your information to handle your order can see it. Each provider may use it only for us and must keep it secure and confidential under a written agreement.",
  "Analytics stays off until you accept it, and never records search text, personal details or payment data.",
  "We check these safeguards regularly and update them as risks change.",
  "If we believe someone has accessed your information without authorisation, we tell you and the Information Regulator as soon as reasonably possible.",
];

function privacyBlocks(document: CustomerPolicyDocument | null): PolicyBlock[] {
  const business = businessFacts(document);
  const contact = contactFacts(document);
  const officer = officerFacts(document);
  const blocks: PolicyBlock[] = [
    // POPIA s18(1)(b): name and address of the responsible party.
    heading("Who we are"),
    paragraph(`${business.legalName}, trading as ${business.tradingName} ("DasKasas", "we"), is responsible for your personal information under the Protection of Personal Information Act 4 of 2013 (POPIA). Address: ${contact.address}. Phone: ${contact.phone}. Email: ${contact.email}.`),
    paragraph("This notice explains what we collect, why, who we share it with, and your rights. It covers our website and our showroom."),
    // s18(1)(a) and (h)(ii): what is collected, and its source when it does not come from you.
    heading("What we collect"),
    paragraph("When you check out: your name, email address and phone number, your delivery address or that you will collect, the pieces you order, and a payment reference."),
    paragraph("When you create an account: your email address and the one-time sign-in codes Clerk sends you. If you save a delivery address, we keep it with your account."),
    paragraph("When you contact us by email, phone or in the showroom: your contact details and what you tell us."),
    paragraph("If you accept optional analytics: which pages and pieces you view, the shop filters you use, how long a product is in view, the website that sent you, and a random visitor number. Analytics never records search text, personal details or payment data."),
    paragraph("From others: Paystack tells us whether your payment went through, and Clerk tells us when you are signed in."),
    heading("Why we use it"),
    ...PURPOSES.map(paragraph),
    // s18(1)(d), (e): voluntary or mandatory, and the consequences of not supplying it.
    heading("What you must give us"),
    paragraph("Checkout needs your name, email address, phone number and, for delivery, your address. Without them we cannot take, deliver or tell you about your order."),
    paragraph("An account is optional. You can check out as a guest."),
    paragraph("Optional analytics is voluntary. If you say no, the shop works the same for you."),
    // s18(1)(f): law requiring the collection or retention.
    heading("Laws that require us to keep information"),
    paragraph("South African tax and company law requires us to keep records of each sale. This includes the Tax Administration Act 28 of 2011, the Companies Act 71 of 2008 and, if we are registered for VAT, the Value-Added Tax Act 89 of 1991. The Consumer Protection Act 68 of 2008 and the Electronic Communications and Transactions Act 25 of 2002 set rules for order records, returns and refunds."),
    heading("Who we share it with"),
    ...RECIPIENTS.map(paragraph),
    heading("Information sent outside South Africa", "outside-south-africa"),
    ...TRANSFERS.map(paragraph),
    heading("How we protect it"),
    ...SAFEGUARDS.map(paragraph),
    // POPIA s14: kept no longer than the purpose or a legal duty needs.
    heading("How long we keep it"),
    paragraph("Order, tax, and payment records are kept for as long as South African tax and accounting law requires and for as long as a return, refund, or dispute about that order is open. Account details are kept while the account is open and then for as long as those legal duties remain. Optional analytics are not collected unless you accept them, and they are not kept for a purpose that acceptance did not cover."),
    // POPIA s69 and POPIA Regulations reg 6.4 (2025): opt-out is not consent.
    heading("Marketing", "marketing"),
    paragraph("We do not send you marketing by email, SMS, WhatsApp or any other electronic message unless you opt in. Opting in means ticking a separate box that is never ticked for you. You can stop at any time, free of charge. Order, delivery and account emails are not marketing."),
    heading("Cookies and optional analytics"),
    paragraph("Without your choice, the shop uses only the storage it needs to work, such as your bag and sign-in. Optional analytics stays off until you choose Accept. You can change your choice at any time with Cookie settings at the bottom of every page."),
    // s18(1)(h)(iii); s23 access (confirmation free), s24 correction and deletion (free, POPIA Regulations reg 3 as amended 2025).
    heading("Your rights"),
    paragraph("Access: you may ask, free of charge, whether we hold personal information about you. You may also ask for a copy or description of it, and of who has had access to it. If a fee applies to a copy, we tell you before we go ahead."),
    paragraph("Correction and deletion: you may ask us, free of charge, to correct or delete information that is wrong, out of date, incomplete, excessive, misleading or obtained unlawfully, or to delete a record we may no longer keep."),
    paragraph("Withdrawing consent: you may withdraw your consent to optional analytics or to marketing at any time."),
    paragraph("Complaints: you may complain to the Information Regulator at any time. Its contact details are below."),
    // s18(1)(h)(iv) and s11(3)-(4); POPIA Regulations reg 2 (2025): notice of the right to object at collection; any channel, free.
    heading("Your right to object", "right-to-object"),
    paragraph("You have the right to object, at any time and free of charge, to our use of your personal information for our legitimate interests, such as security and fraud prevention, and for direct marketing. Once you object, we stop using it for that purpose."),
    paragraph("You can object in any way: by email, SMS, WhatsApp, phone, post or in person. You may use Form 1 in the POPIA Regulations, but you do not have to."),
    // s23-s25 and POPIA Regulations reg 3.4-3.6 (2025): any channel, phone requests recorded, outcome within 30 days.
    heading("How to make a request"),
    paragraph(`Send any privacy request or objection to our Information Officer. Email ${officer.email}, phone ${contact.phone}, or write to or visit ${contact.address}.`),
    paragraph("We may ask you to prove your identity before we share or change information. We record requests made by phone. We tell you what we did within 30 days."),
    // POPIA s55(1).
    heading("Information Officer", "information-officer"),
    paragraph(`Our Information Officer is ${officer.name}. Email: ${officer.email}. Phone: ${contact.phone}. Address: ${contact.address}.`),
    paragraph("The Information Officer makes sure we follow POPIA, deals with your requests, and works with the Information Regulator."),
    heading("Complaints to the Information Regulator", "information-regulator"),
    paragraph("If you are unhappy with how we handle your personal information, please tell us first. You also have the right to complain to the Information Regulator:"),
    ...INFORMATION_REGULATOR.map(paragraph),
    heading("Access to records"),
    paragraph("Our PAIA manual explains how to ask for access to the records we hold."),
  ];
  return document ? blocks : [notice(), ...blocks];
}

// PAIA s51(1)-(3) as substituted by POPIA s110 (30 June 2021). No small-business exemption is in force since 31 Dec 2021 (GeN 397); s90(3) offence.
function paiaBlocks(document: CustomerPolicyDocument | null): PolicyBlock[] {
  const business = businessFacts(document);
  const contact = contactFacts(document);
  const officer = officerFacts(document);
  const blocks: PolicyBlock[] = [
    heading("About this manual"),
    paragraph(`This manual is published under section 51 of the Promotion of Access to Information Act 2 of 2000 (PAIA). It explains how to ask ${business.legalName}, trading as ${business.tradingName} ("DasKasas"), a private body, for access to its records.`),
    // s51(1)(a)(i).
    heading("Contact details of the head of DasKasas"),
    paragraph(`Head and Information Officer: ${officer.name}.`),
    paragraph(`Street address: ${contact.address}.`),
    paragraph(`Postal address: ${officer.postalAddress}.`),
    paragraph(`Phone: ${contact.phone}.`),
    paragraph(`Fax: ${officer.fax}.`),
    paragraph(`Email: ${officer.email}.`),
    // s51(1)(b)(i), s10.
    heading("The Information Regulator's PAIA Guide"),
    paragraph("The Information Regulator publishes a Guide on how to use PAIA, in every official language. It explains how to request a record and what you can do if a request is refused. Get it from the Regulator's website, inforegulator.org.za, or from its offices. Its contact details are at the end of this manual."),
    // s51(1)(b)(ii), s52.
    heading("Records available without a request"),
    paragraph("We have not published a notice under section 52. You can read these records on this website without a request: our terms and conditions, delivery, return and refund policies, privacy policy, this manual, and product details and prices."),
    // s51(1)(b)(iii).
    heading("Records kept under other laws"),
    paragraph("We keep records under these laws, where they apply to us: the Companies Act 71 of 2008, the Income Tax Act 58 of 1962, the Tax Administration Act 28 of 2011, the Value-Added Tax Act 89 of 1991, the Consumer Protection Act 68 of 2008, the Electronic Communications and Transactions Act 25 of 2002 and the Protection of Personal Information Act 4 of 2013. If we have employees, also the Basic Conditions of Employment Act 75 of 1997, the Unemployment Insurance Act 63 of 2001 and the Skills Development Levies Act 9 of 1999."),
    // s51(1)(b)(iv).
    heading("Subjects and categories of records"),
    paragraph("Company: registration documents, directors' records, minutes and resolutions."),
    paragraph("Finance and tax: accounting records, invoices, bank statements, and tax and VAT returns."),
    paragraph("Customers: orders, payments and refunds, delivery and collection details, returns, faults, correspondence and accounts."),
    paragraph("Products and suppliers: the catalogue, stock, prices, suppliers, purchase orders and made-to-order commissions."),
    paragraph("Staff, if we have staff: employment contracts, pay, leave and tax records."),
    paragraph("Website and systems: website content, analytics from visitors who accepted it, and security logs."),
    // PAIA s53 (form and contents), s54 (fees; no request fee for a personal requester), s56-s57 (30 days, one extension), Part 3 Ch 4 (refusal grounds), s77A/s78 (remedies).
    heading("How to request a record"),
    paragraph("Use Form 2 (Request for Access to Record) in the PAIA Regulations, 2021, available on the Information Regulator's website. Send it to the head of DasKasas using the contact details above."),
    paragraph("Describe the record well enough for us to find it, and say how you want access. Say which right you want to exercise or protect and why you need the record for it. If you ask on someone else's behalf, show that you may act for them."),
    paragraph("A request fee and access fees set in the PAIA Regulations may apply. We tell you about any fee before we go further. There is no request fee when you ask for your own personal information."),
    paragraph("We decide within 30 days and tell you in writing. We may extend this once, by up to 30 days, and we tell you why. We may refuse only on the grounds PAIA allows, such as protecting another person's privacy or commercial information."),
    paragraph("If you disagree with our decision, you may complain to the Information Regulator or apply to court."),
    // s51(1)(c)(i)-(v).
    heading("Personal information we process"),
    paragraph("Purposes: to take, deliver and support orders, run customer accounts, keep the records the law requires, keep the shop secure, and, only with consent, measure which pieces and filters are useful. The privacy policy sets out the lawful basis for each."),
    paragraph("People and information: customers and website visitors (names, contact details, delivery addresses, orders, payment references, accounts, and analytics if accepted); suppliers and makers (business and contact details, bank details and orders); staff, if we have staff (identity, contact, employment, pay and tax details)."),
    paragraph("Recipients: Paystack, SendGrid, Clerk, Railway and PostHog as described in the privacy policy, whoever delivers an order, our professional advisers such as accountants, and public bodies when the law requires, such as the South African Revenue Service."),
    paragraph("Planned transfers outside South Africa: to Clerk, SendGrid and Railway in the United States, PostHog in the European Union, and Paystack in Nigeria when a payment is not processed in South Africa. The privacy policy gives the POPIA section 72 ground for each."),
    paragraph(`Security measures: ${SAFEGUARDS.join(" ")}`),
    // s51(2)-(3).
    heading("Availability of this manual"),
    paragraph(`This manual is on our website at ${WEBSITE}/policies/paia. You can inspect a copy at ${contact.address} during business hours. We give a copy to anyone who asks, for a reasonable fee, and to the Information Regulator on request. We update the manual regularly.`),
    heading("Information Regulator"),
    ...INFORMATION_REGULATOR.map(paragraph),
  ];
  return document ? blocks : [notice(), ...blocks];
}

export function policyPage(document: CustomerPolicyDocument | null, section: PolicySection): PolicyView {
  if (section === "delivery") return view(section, document !== null, deliveryBlocks(document));
  if (section === "returns") return view(section, document !== null, returnBlocks(document));
  if (section === "refunds") return view(section, document !== null, refundBlocks(document));
  if (section === "terms") return view(section, document !== null, termsBlocks(document));
  if (section === "paia") return view(section, document !== null, paiaBlocks(document));
  return view(section, document !== null, privacyBlocks(document));
}
