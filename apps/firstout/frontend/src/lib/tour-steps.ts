/**
 * Firstout app-tour steps. Single source of truth for the joyride.
 *
 * Anchors: `[data-tour]` on the shell header and home cockpit.
 * Page steps spotlight `#main-content h1` after navigation.
 * Replay: header "App tour" button and Profile → Replay walkthrough.
 */

export type TourStepDefinition = {
  id: string;
  title: string;
  content: string;
  /** CSS selector spotlight. Page steps retarget the main heading at runtime. */
  target: string;
  route?: string;
  /** Main heading that must be on screen before the step opens. */
  heading?: string;
  placement?: "top" | "bottom" | "left" | "right" | "center";
  isFixed?: boolean;
  /** Open the side rail so section labels are visible. */
  expandNav?: boolean;
};

export const TOUR_STEPS: TourStepDefinition[] = [
  {
    id: "welcome",
    route: "/",
    heading: "Home",
    target: "body",
    placement: "center",
    isFixed: true,
    title: "Welcome to Firstout",
    content:
      "This is the shop back office: catalogue and stock, the showroom till, customer documents, and the ZAR ledger. The tour follows a piece of furniture from the supplier invoice to the tax invoice. Skip tour closes it at any step, and Escape does the same. Open it again from the tour button in the header, or from Profile.",
  },
  {
    id: "side-nav",
    route: "/",
    heading: "Home",
    target: ".firstout-side-nav",
    placement: "right",
    isFixed: true,
    expandNav: true,
    title: "Sections in the rail",
    content:
      "Home is the stock cockpit. Catalogue holds SKUs, suppliers, price lists, proformas, and locations. Stock is stocktakes, adjustments, CSV import, and reorder. Warehouse runs purchase orders, transit, receive, transfers, and picks. Till sells on the floor. Sales covers quotes, orders, laybys, customers, returns, and deliveries. Books is the chart of accounts through VAT201. Admin is users, roles, audit, profile, and settings.",
  },
  {
    id: "home-actions",
    route: "/",
    heading: "Home",
    target: "[data-tour='home-actions']",
    placement: "bottom",
    title: "Start a job from Home",
    content:
      "New stock creates a SKU, with optional opening quantity that does not post a journal. Stocktake counts one location and locks it while the count is open. Stock adjustment changes on-hand and posts one balanced journal. Import CSV creates or updates SKUs and can set on-hand. New layby and Process return jump straight into sales.",
  },
  {
    id: "home-kpis",
    route: "/",
    heading: "Home",
    target: "[data-tour='home-kpis']",
    placement: "top",
    title: "What the cockpit numbers mean",
    content:
      "On order is quantity still inbound. It is not sellable. On hand is units in locations at landed cost. Aged stock is on-hand value that has not moved for more than 180 days. Open laybys are status open or ready. Low-stock SKUs have 1 or 2 units on hand in total. Returns open are draft RMAs waiting to be completed or cancelled.",
  },
  {
    id: "home-attention",
    route: "/",
    heading: "Home",
    target: "[data-tour='home-attention']",
    placement: "top",
    title: "What needs a person",
    content:
      "Needs attention lists up to eight items: low-stock SKUs, in-progress stocktakes, draft returns, overdue laybys, and unmatched bank lines. Each row opens the page that clears it. Recent movements are the latest unit-cost events — receive, land, till, transfer, adjustment — so you can see what just changed quantity or cost.",
  },
  {
    id: "search",
    route: "/",
    heading: "Home",
    target: "[data-tour='header-search']",
    placement: "bottom",
    isFixed: true,
    title: "Search the shop",
    content:
      "Header search matches SKUs by barcode, name, or our ref, plus purchase orders and invoices. Choose a hit to open that record. It does not search customers, laybys, or journals — use the rail for those lists.",
  },
  {
    id: "catalogue",
    route: "/catalogue",
    heading: "Catalogue",
    target: "#main-content h1",
    placement: "bottom",
    title: "Catalogue",
    content:
      "Every sellable product is a SKU: our ref, our barcode, name, design, and fabric. Retail and wholesale prices are stored ex-VAT; the screen shows inc-VAT at 15%. Our barcode is what the till and shelf labels scan. Supplier ref is the factory’s code — keep them separate. A preferred supplier, lead time, and photo live on the SKU. Opening stock is optional and does not post to the ledger.",
  },
  {
    id: "purchase-orders",
    route: "/purchase-orders",
    heading: "Purchase orders",
    target: "#main-content h1",
    placement: "bottom",
    title: "Buying stock",
    content:
      "A purchase order uses our number (PO-0001) and can point at a supplier proforma. Mark it on water when it ships, then land it with the exchange rate and the factory, freight, and clearance bills. Landed cost is split across lines by factory value and stored in ZAR. On-hand does not increase until the order is received at a location. Over the approval threshold, a purchase order waits for someone who can manage users.",
  },
  {
    id: "receive",
    route: "/receive",
    heading: "Receive",
    target: "#main-content h1",
    placement: "bottom",
    title: "Receive into a location",
    content:
      "Receive posts a landed purchase order into a location such as the warehouse. Quantity lands on that location’s default FLOOR bin unless you scan another bin code. Unit cost blends with stock already there. A location locked for stocktake cannot receive. The Warehouse page has the same receive flow for the floor, with a scanner.",
  },
  {
    id: "transfers",
    route: "/transfers",
    heading: "Transfers",
    target: "#main-content h1",
    placement: "bottom",
    title: "Move stock between locations",
    content:
      "A transfer is a document, not an instant quantity swap. Create a draft, dispatch it (source on-hand drops), then receive it at the destination (destination on-hand rises, using the cost captured at dispatch). Until receive, the units are in transit. Cancel a draft without touching stock. Cancelling in transit restocks the source and is limited to people who manage users.",
  },
  {
    id: "till",
    route: "/till",
    heading: "Till",
    target: "#main-content h1",
    placement: "bottom",
    title: "Sell on the floor",
    content:
      "Scan our barcode or type it. Lines use retail inc-VAT, or wholesale for a trade customer when a wholesale price is set. A line discount needs the discount permission and must stay inside the shop cap. Tender is cash, card, or deposit — the app records the payment in the ledger and does not charge a card machine. VAT is 15% on the discounted ex-VAT total. A kit that is not fully at this showroom needs a pick before it can sell.",
  },
  {
    id: "customers",
    route: "/customers",
    heading: "Customers",
    target: "#main-content h1",
    placement: "bottom",
    title: "Customers",
    content:
      "Retail and trade customers live here, with phone, price tier, credit limit, and on hold. Open and overdue totals are calculated from invoices, not stored as a flag. A customer on hold, or over their credit limit, blocks a till sale and a books invoice unless someone with permission records an override reason. Walk-in is the unnamed floor customer and skips that gate.",
  },
  {
    id: "laybys",
    route: "/laybys",
    heading: "Laybys",
    target: "#main-content h1",
    placement: "bottom",
    title: "Laybys",
    content:
      "A layby reserves a sale for a named customer. Deposits post to customer deposits, not to the till’s deposit tender. Hold stock only at a showroom: on-hand drops when you create it and comes back if you cancel. Complete it once it is ready — that raises the tax invoice, applies the deposits, and posts cost of goods. Overdue means the due date has passed. It is not a separate status.",
  },
  {
    id: "invoices",
    route: "/invoices",
    heading: "Invoices",
    target: "#main-content h1",
    placement: "bottom",
    title: "Tax invoices and the ledger",
    content:
      "A books invoice is the customer tax invoice. Posting it writes a balanced journal: accounts receivable, sales, and VAT. Send it by email with the PDF attached, or by WhatsApp, from the document itself. One credit note reverses one invoice. Supplier bills, including foreign currency at a rate you type, live under Bills. Payments record money in or out — they do not start an EFT.",
  },
  {
    id: "bank",
    route: "/bank-reconciliation",
    heading: "Bank reconciliation",
    target: "#main-content h1",
    placement: "bottom",
    title: "Bank reconciliation",
    content:
      "Import a bank CSV with a date, a description, and either a signed amount or separate debit and credit columns. Match a line to a payment or a journal. Unmatched lines stay on the list. Rules can suggest a coding; you confirm before they apply. Nothing here connects to the bank or moves money.",
  },
  {
    id: "reports",
    route: "/reports",
    heading: "Reports",
    target: "#main-content h1",
    placement: "bottom",
    title: "Reports",
    content:
      "Stock valuation and aged stock, sales by SKU, and a sales VAT summary each export to CSV. Financial reports cover aged receivables and payables, profit and loss, balance sheet, trial balance, journals, and cash. Lead-time reports use real purchase-order dates. Criticality ranks SKUs by ex-VAT sales, with A covering the first 80% of value. These pages prepare figures. They do not file with SARS.",
  },
  {
    id: "vat201",
    route: "/vat201",
    heading: "VAT201",
    target: "#main-content h1",
    placement: "bottom",
    title: "VAT201 draft",
    content:
      "A VAT201 period snapshots the draft return for a date range so someone can type it into eFiling. Locking the period can also lock the matching books period, which then blocks new journals and stock movements on those dates. Reopening the VAT period does not unlock the books. The app never calls SARS.",
  },
  {
    id: "settings",
    route: "/settings",
    heading: "Settings",
    target: "#main-content h1",
    placement: "bottom",
    title: "Shop settings",
    content:
      "Settings holds the legal name, VAT number, and logo printed on tax invoices, plus document prefixes, session length, the till discount cap, and the purchase-order approval threshold. Communications is the shop mailbox and WhatsApp. Pick priority chooses which location a kit pick drains first.",
  },
  {
    id: "replay",
    target: "[data-tour='header-tour']",
    placement: "bottom",
    isFixed: true,
    title: "Open this tour again",
    content:
      "This button restarts the walkthrough from the welcome step. Profile has the same action under App tour. Skipping or finishing stores that choice in this browser, so the tour will not open by itself the next time you sign in on this device.",
  },
];

export function stepsForUser(): TourStepDefinition[] {
  return TOUR_STEPS;
}
