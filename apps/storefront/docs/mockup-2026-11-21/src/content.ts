// Every fact the shop renders. Showroom details: Google Maps listing "DasKasas Bedford
// Square" and the Bedford Centre directory (checked 21 Nov 2026). Catalogue: the six pieces
// published on daskasas.co.za/shop. Unknown facts are left out, never invented.
import type { Page, Route } from '@/lib/router';

// ------------------------------------------------------------------- showroom

/**
 * The one place the showroom address lives. Google gives the unit as GL15; the Bedford
 * Centre directory gives LG15. Correct it here if needed.
 */
export const SHOWROOM_ADDRESS = 'Shop GL15, Bedford Square, Smith Road, Bedfordview, Johannesburg, 2007';

const addressParts = SHOWROOM_ADDRESS.split(', ');

export const showroom = {
  name: 'DasKasas, Bedford Square',
  address: SHOWROOM_ADDRESS,
  /** "Shop GL15, Bedford Square, Bedfordview": unit, centre and suburb from the address. */
  short: [addressParts[0], addressParts[1], addressParts[3]].join(', '),
  note: 'Bedford Square is inside Bedford Centre.',
  hours: [
    { days: 'Monday to Friday', short: 'Mon–Fri', time: '09:00–18:00' },
    { days: 'Saturday', short: 'Sat', time: '09:00–17:00' },
    { days: 'Sunday', short: 'Sun', time: '09:00–15:00' },
  ],
  phones: [
    { label: 'Mobile', number: '+27 63 025 4010' },
    { label: 'Showroom', number: '010 745 1980' },
  ],
  email: 'Cindy@daskasas.co.za',
  website: 'daskasas.co.za',
};

export const hoursLine = showroom.hours.map((h) => `${h.short} ${h.time}`).join(', ');
export const phonesLine = showroom.phones.map((p) => `${p.number} (${p.label.toLowerCase()})`).join(' or ');

export const brand = {
  name: 'DasKasas',
  summary: 'Furniture for living and dining rooms, from our showroom in Bedford Square, Bedfordview.',
  copyright: `© 2026 DasKasas · ${showroom.website}`,
};

export const photos = {
  front: { src: 'arc-front.jpg', alt: 'Arc sofa, seen from the front at an angle' },
  angle: { src: 'arc-angle.jpg', alt: 'Arc sofa, seen from the right' },
  detail: { src: 'arc-detail.jpg', alt: 'Close-up of the Arc sofa’s arm, cushion and plinth' },
} as const;

export type PhotoRef = { src: string; alt: string; position?: string };

/** Crops of arc-detail.jpg (object-position), for slots that need a different view. */
export const crops = {
  plinth: { ...photos.detail, alt: 'Arc sofa plinth, close up', position: '50% 100%' },
  cushion: { ...photos.detail, alt: 'Arc sofa seat cushion, close up', position: '85% 50%' },
} satisfies Record<string, PhotoRef>;

const zar = new Intl.NumberFormat('en-ZA', { style: 'currency', currency: 'ZAR' });
export const formatPrice = (rand: number) => zar.format(rand);

// ------------------------------------------------------------------ catalogue

export type Room = 'Sofas' | 'Dining Room' | 'Living room' | 'Bedroom';
export const rooms: Room[] = ['Sofas', 'Dining Room', 'Living room', 'Bedroom'];
export type Availability = 'In stock' | 'Made to order';

export interface Piece {
  sku: string;
  name: string;
  /** Rand, VAT included. */
  price: number;
  stock: number;
  room: Room;
  /** Only what the catalogue name states. */
  details: string[];
}

export const pieces: Piece[] = [
  { sku: '60244', name: 'Penelope Dining Chair', price: 3825.22, stock: 2, room: 'Dining Room', details: [] },
  {
    sku: '33343',
    name: 'Bedside Table, 3 drawers',
    price: 6877.39,
    stock: 1,
    room: 'Bedroom',
    details: ['Three drawers', 'Size: 76 × 45 × 68 cm'],
  },
  {
    sku: 'P00300',
    name: 'Coffee Table, Ostrich Leather',
    price: 7817.39,
    stock: 1,
    room: 'Living room',
    details: ['Ostrich leather'],
  },
  {
    sku: 'P00342AD',
    name: 'Jinja Dining Table, Solid Veneer Top',
    price: 34773.92,
    stock: 1,
    room: 'Dining Room',
    details: ['Solid veneer top', 'Size: 2600 × 1200 mm'],
  },
  {
    sku: 'P00332AD',
    name: 'Jinja Dining Table, Glass Top',
    price: 37382.61,
    stock: 2,
    room: 'Dining Room',
    details: ['Glass top', 'Size: 2400 × 1200 mm'],
  },
  {
    sku: 'P003340AD',
    name: 'L’Opulence Wooden Dining Table',
    price: 69556.52,
    stock: 1,
    room: 'Dining Room',
    details: ['Wood', 'Size: 230 × 120 cm'],
  },
];

export const pieceRoute = (p: Piece) => `p-${p.sku.toLowerCase()}` as Page;
export const findPiece = (page: string) => pieces.find((p) => pieceRoute(p) === page);
export const stockLabel = (p: Piece) => `${p.stock} in stock`;

/** The photographed demo piece. No price; enquiries only. */
export const arc = {
  name: 'Arc sofa',
  room: 'Sofas' as Room,
  availability: 'Made to order' as Availability,
  priceLabel: 'Price on request',
  short: 'A curved three-seater, made to order.',
  fill: 'Available with a Soft or Firm cushion fill',
  photos: [photos.front, photos.angle, photos.detail],
};

/** Where every "Ask about this piece" button goes. */
export const askRoute: Route = 'help/contact';

/** One shape for every listing card, Arc included. */
export interface ListItem {
  id: string;
  name: string;
  room: Room;
  availability: Availability;
  /** null for the Arc sofa (price on request). */
  price: number | null;
  priceLabel: string;
  stockLabel: string;
  description: string;
  to: Page;
  photo?: PhotoRef;
  placeholder: string;
  piece?: Piece;
}

export const pieceItem = (p: Piece): ListItem => ({
  id: p.sku,
  name: p.name,
  room: p.room,
  availability: 'In stock',
  price: p.price,
  priceLabel: formatPrice(p.price),
  stockLabel: stockLabel(p),
  description: p.details.length ? p.details.join(' · ') : p.room,
  to: pieceRoute(p),
  placeholder: p.name,
  piece: p,
});

export const arcItem: ListItem = {
  id: 'arc',
  name: arc.name,
  room: arc.room,
  availability: arc.availability,
  price: null,
  priceLabel: arc.priceLabel,
  stockLabel: arc.availability,
  description: arc.short,
  to: 'arc',
  photo: photos.front,
  placeholder: arc.name,
};

/** Arc first, then the catalogue in its published order. */
export const allItems: ListItem[] = [arcItem, ...pieces.map(pieceItem)];

/** Other real pieces for cross-sells: same room first. */
export const relatedTo = (room: Room, excludeId: string, n = 4) =>
  [...allItems]
    .filter((i) => i.id !== excludeId && i.piece)
    .sort((a, b) => Number(b.room === room) - Number(a.room === room))
    .slice(0, n);

// -------------------------------------------------------------------- listings

export type ListingPage = 'shop' | 'sofas' | 'dining-room' | 'on-sale';

export interface Listing {
  page: ListingPage;
  name: string;
  subtitle: string;
  description: string;
  items: ListItem[];
  photo?: PhotoRef;
}

export const listings: Record<ListingPage, Listing> = {
  shop: {
    page: 'shop',
    name: 'Shop',
    subtitle: 'Everything in our catalogue.',
    description: 'Every piece, for every room.',
    items: allItems,
  },
  sofas: {
    page: 'sofas',
    name: 'Sofas',
    subtitle: 'Sofas for the living room.',
    description: 'Sofas for the living room.',
    items: allItems.filter((i) => i.room === 'Sofas'),
    photo: photos.angle,
  },
  'dining-room': {
    page: 'dining-room',
    name: 'Dining Room',
    subtitle: 'Dining tables and chairs.',
    description: 'Dining tables and chairs.',
    items: allItems.filter((i) => i.room === 'Dining Room'),
  },
  'on-sale': {
    page: 'on-sale',
    name: 'On Sale',
    subtitle: 'Everything available to buy now.',
    description: 'Everything available to buy now.',
    items: allItems.filter((i) => i.piece),
  },
};

export const countLabel = (n: number) => `${n} ${n === 1 ? 'piece' : 'pieces'}`;

export const nav: { label: string; to: Page }[] = [
  { label: 'Shop', to: 'shop' },
  { label: 'Sofas', to: 'sofas' },
  { label: 'Dining Room', to: 'dining-room' },
  { label: 'On Sale', to: 'on-sale' },
  { label: 'Help', to: 'help' },
];

export const announcement = {
  text: 'Visit our showroom at Bedford Square, Bedfordview.',
  detail: 'Open seven days a week.',
  to: 'home/visit' as Route,
};

// --------------------------------------------------------------------- policies

export const policy = {
  delivery: 'We deliver in selected Gauteng areas.',
  deliveryCharges:
    'Delivery charges are shown in rand, including VAT, and confirmed in your order total before payment.',
  collection: `Or collect from our showroom at ${showroom.short}.`,
  contactFirst: 'Contact us with your order number before sending anything back. We agree a collection or drop-off first.',
  changeOfMind:
    'Within 30 days of delivery or collection, if the piece is unused, in its original condition and packaging, with tags on and with the invoice or delivery note.',
  collectionFee:
    'If we collect, we quote a collection fee before booking. There is no fee if you bring it to the showroom. The original delivery charge is not refunded on a change of mind.',
  notReturnable:
    'Bespoke or personalised pieces, and pieces made to a measurement, fabric or finish chosen for your order.',
  wrongItem:
    'Wrong, missing parts or not as described: we collect at no charge and refund the piece and its delivery charge.',
  faulty:
    'Claims for faulty furniture within 12 months of purchase, under the Consumer Protection Act. We may quote an assessment fee first; it is refunded if the fault is confirmed. You choose repair, replacement or refund.',
  markings: 'Natural markings in leather and solid wood are not faults.',
};

// ------------------------------------------------------------------------- FAQ

export const faqs: { question: string; answer: string }[] = [
  {
    question: 'Where is your showroom?',
    answer: `${showroom.address}. ${showroom.note} We are open ${showroom.hours
      .map((h) => `${h.days} ${h.time}`)
      .join(', ')}.`,
  },
  {
    question: 'Do you deliver?',
    answer: `Yes, in selected Gauteng areas. ${policy.deliveryCharges} You can also collect from the showroom.`,
  },
  {
    question: 'Do I need an account to order?',
    answer: 'No. You check out as a guest.',
  },
  {
    question: 'Do prices include VAT?',
    answer: 'Yes. All prices are in rand and include VAT.',
  },
  {
    question: 'Can I return a piece?',
    answer: `Yes, for a change of mind within 30 days of delivery or collection, if it is unused and in its original condition and packaging. ${policy.contactFirst}`,
  },
  {
    question: 'What if a piece is faulty?',
    answer: policy.faulty,
  },
  {
    question: 'What is On Sale?',
    answer: 'Everything that is available to buy now. It is not a discount.',
  },
  {
    question: 'How do I contact you?',
    answer: `Call ${phonesLine}, or email ${showroom.email}.`,
  },
];

// --------------------------------------------------------------- bag, checkout

export const bagCopy = {
  title: 'Your bag',
  empty: 'Your bag is empty.',
  deliveryNote: `Delivery in selected Gauteng areas, or collect from our showroom at ${showroom.short}.`,
  deliveryCost: 'Confirmed before payment',
  totalNote: 'Plus delivery, if you choose it. VAT included.',
  checkout: 'Checkout',
  continue: 'Continue shopping',
};

export const checkout = {
  title: 'Checkout',
  guestNote: 'Guest checkout. No account needed.',
  methods: [
    {
      id: 'delivery',
      label: 'Delivery',
      description: 'Selected Gauteng areas. The delivery charge is confirmed in your order total before payment.',
    },
    {
      id: 'collect',
      label: 'Collection',
      description: `Collect from our showroom at ${showroom.short}. Open ${hoursLine}.`,
    },
  ],
  notPlaced: 'Orders can’t be placed from this preview.',
};

export const contactCopy = {
  notSent: 'Messages can’t be sent from this preview.',
};

// ---------------------------------------------------------------------- footer

export interface FooterColumn {
  title: string;
  links: { label: string; to: Route }[];
}

export const footer = {
  blurb: brand.summary,
  columns: [
    {
      title: 'Shop',
      links: [
        { label: 'Shop all', to: 'shop' },
        { label: 'Sofas', to: 'sofas' },
        { label: 'Dining Room', to: 'dining-room' },
        { label: 'On Sale', to: 'on-sale' },
      ],
    },
    {
      title: 'Help',
      links: [
        { label: 'Delivery and collection', to: 'help' },
        { label: 'Returns', to: 'help/returns' },
        { label: 'Contact us', to: 'help/contact' },
      ],
    },
    {
      title: 'Your order',
      links: [
        { label: 'Bag', to: 'bag' },
        { label: 'Checkout', to: 'checkout' },
      ],
    },
  ] satisfies FooterColumn[],
  visit: {
    title: 'Visit us',
    lines: [
      SHOWROOM_ADDRESS,
      ...showroom.hours.map((h) => `${h.days}: ${h.time}`),
      ...showroom.phones.map((p) => `${p.label}: ${p.number}`),
      showroom.email,
    ],
  },
  bottomLinks: [
    { label: 'Help', to: 'help' },
    { label: 'Contact us', to: 'help/contact' },
  ] satisfies { label: string; to: Route }[],
};
