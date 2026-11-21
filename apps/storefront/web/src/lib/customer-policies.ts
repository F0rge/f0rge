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
  email: policyPlaceholder("support email"),
  phone: policyPlaceholder("phone number"),
  address: policyPlaceholder("physical address"),
  delivery: policyPlaceholder("delivery areas, lead times, and VAT-inclusive ZAR shipping rates"),
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
    { href: "/help#contact", label: "Contact" },
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
    { href: "/help#contact", label: "Contact" },
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
    paragraph("The storefront is built to use these operators: Clerk for account sign-in, PostHog for optional analytics, Paystack for card payments, SendGrid for transactional email, and Railway for hosting. Each operator may process the personal information needed for that role. This list is the set the software is built for and should be confirmed before go-live."),
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
