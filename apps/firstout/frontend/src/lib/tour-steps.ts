/**
 * Page tours teach the task on the current screen.
 * The overview is the long walk across the shop and is started on purpose.
 * Steps spotlight the control you use. They do not retarget the page heading.
 */

export type TourStepDefinition = {
  id: string;
  title: string;
  content: string;
  /** CSS selector for the control this step teaches. */
  target: string;
  route?: string;
  /** Path must match exactly (no nested record pages). */
  exact?: boolean;
  placement?: "top" | "bottom" | "left" | "right" | "center";
  isFixed?: boolean;
  /** Open the side rail so section labels are visible. */
  expandNav?: boolean;
  /**
   * Click this control only when `target` is not visible yet.
   * Used to open a create modal without resetting a form that is already open.
   */
  open?: string;
};

export type PageTour = {
  id: string;
  route: string;
  exact: boolean;
  steps: TourStepDefinition[];
};

/** Primary action inside the Carbon modal that is actually open. */
export const MODAL_SAVE = ".cds--modal.is-visible .cds--btn--primary";

function step(
  id: string,
  title: string,
  content: string,
  target: string,
  extra?: Partial<TourStepDefinition>,
): TourStepDefinition {
  return { id, title, content, target, placement: "bottom", ...extra };
}

function modal(open: string, placement: TourStepDefinition["placement"] = "bottom") {
  return { open, placement };
}

export const PAGE_TOURS: PageTour[] = [
  {
    id: "home",
    route: "/",
    exact: true,
    steps: [
      step("home-actions", "Start a job", "New stock, a count, an adjustment, import, a layby, or a return.", "[data-tour='home-actions']"),
      step("home-kpis", "Shop totals", "Open a tile to work that list.", "[data-tour='home-kpis']", { placement: "top" }),
      step("home-attention", "Needs a person", "Each row opens the record that needs a person.", "[data-tour='home-attention']", { placement: "top" }),
    ],
  },
  {
    id: "catalogue",
    route: "/catalogue",
    exact: true,
    steps: [
      step("catalogue-search", "Find a SKU", "Filter by name, our ref, or barcode.", "#catalogue-search"),
      step("catalogue-new", "New SKU", "Create a SKU.", "[data-tour='catalogue-new']"),
    ],
  },
  {
    id: "catalogue-new",
    route: "/catalogue/new",
    exact: true,
    steps: [
      step("sku-ref", "Our ref", "The shop code for this SKU.", "#new-sku-our-ref"),
      step("sku-name", "Name", "This name prints on documents.", "#new-sku-name"),
      step("sku-category", "Category", "Category groups the SKU. A stocktake can count one category.", "#new-sku-category"),
      step("sku-price", "Retail price", "Retail price including VAT.", "#new-sku-retail-inc-vat"),
      step("sku-save", "Save", "Save the SKU.", "[data-tour='sku-save']", { placement: "top" }),
    ],
  },
  {
    id: "suppliers",
    route: "/suppliers",
    exact: true,
    steps: [
      step("supplier-new", "Add supplier", "Add a supplier.", "[data-tour='supplier-new']"),
      step("supplier-name", "Name", "Enter the supplier name.", "#create-supplier-name", modal("[data-tour='supplier-new']")),
      step("supplier-save", "Save", "Save the supplier.", MODAL_SAVE, modal("[data-tour='supplier-new']", "top")),
    ],
  },
  {
    id: "price-lists",
    route: "/price-lists",
    exact: true,
    steps: [
      step("price-list-new", "New price list", "Create a named price list.", "[data-tour='price-list-new']"),
      step("price-list-name", "Name", "Name the list, then save.", "#create-price-list-name", modal("[data-tour='price-list-new']")),
      step("price-list-save", "Save", "Save the price list.", MODAL_SAVE, modal("[data-tour='price-list-new']", "top")),
    ],
  },
  {
    id: "proformas",
    route: "/proformas",
    exact: true,
    steps: [
      step("proforma-new", "File a proforma", "File a supplier proforma.", "[data-tour='proforma-new']"),
      step("proforma-supplier", "Supplier", "Choose the supplier and attach the PDF.", "#proforma-supplier", modal("[data-tour='proforma-new']")),
      step("proforma-save", "Save", "Save the proforma.", MODAL_SAVE, modal("[data-tour='proforma-new']", "top")),
    ],
  },
  {
    id: "locations",
    route: "/locations",
    exact: true,
    steps: [
      step("location-new", "Add location", "Add a warehouse or showroom.", "[data-tour='location-new']"),
      step("location-name", "Name", "Name the location.", "#create-location-name", modal("[data-tour='location-new']")),
      step("location-save", "Save", "Save the location.", MODAL_SAVE, modal("[data-tour='location-new']", "top")),
    ],
  },
  {
    id: "stocktakes",
    route: "/stocktakes",
    exact: true,
    steps: [
      step("stocktake-location", "Location", "Choose the location to count.", "#stocktake-location"),
      step("stocktake-category", "Category", "Count one category, such as Sofas, or leave this as all.", "#stocktake-category"),
      step("stocktake-start", "Start", "Start the count. This location stays locked until you post.", "[data-tour='stocktake-start']"),
    ],
  },
  {
    id: "adjustments",
    route: "/adjustments",
    exact: true,
    steps: [
      step("adjustment-location", "Location", "Choose the location to adjust.", "#adjustment-location"),
      step("adjustment-reason", "Reason", "Pick a reason, then start the draft.", "#adjustment-reason"),
      step("adjustment-start", "Start draft", "Start the draft. Post it when the lines are right.", "[data-tour='adjustment-start']"),
    ],
  },
  {
    id: "import",
    route: "/import",
    exact: true,
    steps: [
      step("import-inventory", "Inventory file", "Choose the inventory CSV. Stock on hand is optional.", "[data-tour='import-inventory']"),
      step("import-start", "Import", "Start the import.", "[data-tour='import-start']"),
    ],
  },
  {
    id: "reorder",
    route: "/reorder",
    exact: true,
    steps: [
      step("reorder-create", "Draft purchase order", "Select low-stock SKUs, then create a draft PO.", "[data-tour='reorder-create']"),
    ],
  },
  {
    id: "purchase-orders",
    route: "/purchase-orders",
    exact: true,
    steps: [
      step("po-filter", "Filter", "Filter the list by status.", "#po-status-filter"),
      step("po-new", "Raise PO", "Raise a purchase order.", "[data-tour='po-new']"),
      step("po-supplier", "Supplier", "Choose the supplier.", "#po-supplier", modal("[data-tour='po-new']")),
      step("po-save", "Save", "Save the purchase order.", MODAL_SAVE, modal("[data-tour='po-new']", "top")),
    ],
  },
  {
    id: "transit",
    route: "/transit",
    exact: true,
    steps: [
      step("transit-list", "In transit", "Open a PO that is on water or landed, then receive it.", "[data-tour='transit-list']"),
    ],
  },
  {
    id: "receive",
    route: "/receive",
    exact: true,
    steps: [
      step("receive-po", "Purchase order", "Choose the landed purchase order.", "#receive-po"),
      step("receive-location", "Location", "Choose the location that receives the stock.", "#receive-location"),
      step("receive-submit", "Receive", "Receive into that location.", "[data-tour='receive-submit']"),
    ],
  },
  {
    id: "transfers",
    route: "/transfers",
    exact: true,
    steps: [
      step("transfer-from", "From", "Choose the source location.", "#transfer-from"),
      step("transfer-to", "To", "Choose the destination.", "#transfer-to"),
      step("transfer-save", "Save draft", "Save the draft, then dispatch and receive it.", "[data-tour='transfer-save']"),
    ],
  },
  {
    id: "picks",
    route: "/picks",
    exact: true,
    steps: [
      step("pick-new", "New pick", "Start a pick.", "[data-tour='pick-new']"),
      step("pick-kit", "Kit", "Choose the kit to pick.", "#pick-kit", modal("[data-tour='pick-new']")),
      step("pick-qty", "Quantity", "Enter the quantity.", "#pick-qty", modal("[data-tour='pick-new']")),
      step("pick-save", "Save", "Save the pick.", MODAL_SAVE, modal("[data-tour='pick-new']", "top")),
    ],
  },
  {
    id: "wms",
    route: "/wms",
    exact: true,
    steps: [
      step("wms-stocktake", "Count", "Start a count at your standing location, then scan each SKU.", "[data-tour='wms-stocktake']"),
    ],
  },
  {
    id: "till",
    route: "/till",
    exact: true,
    steps: [
      step("till-location", "Showroom", "Choose the showroom.", "#till-location"),
      step("till-scan", "Scan", "Scan our barcode.", "#till-scan"),
      step("till-add", "Add", "Add the line to the cart, then tender.", "[data-tour='till-add']"),
    ],
  },
  {
    id: "quotes",
    route: "/quotes",
    exact: true,
    steps: [
      step("quote-new", "New quote", "Start a quote.", "[data-tour='quote-new']"),
      step("quote-customer", "Customer", "Choose the customer.", "#quote-customer", modal("[data-tour='quote-new']")),
      step("quote-sku", "Item", "Add a SKU and quantity.", "#quote-sku-0", modal("[data-tour='quote-new']")),
      step("quote-save", "Save", "Save the quote.", MODAL_SAVE, modal("[data-tour='quote-new']", "top")),
    ],
  },
  {
    id: "orders",
    route: "/orders",
    exact: true,
    steps: [
      step("orders-handoffs", "Storefront orders", "Import, collect, or refund a storefront order from this list.", "[data-tour='storefront-handoffs']"),
    ],
  },
  {
    id: "laybys",
    route: "/laybys",
    exact: true,
    steps: [
      step("layby-new", "New layby", "Start a layby.", "[data-tour='layby-new']"),
      step("layby-customer", "Customer", "Choose the customer, or type a new name.", "#layby-customer", modal("[data-tour='layby-new']")),
      step("layby-sku", "Item", "Choose the SKU and quantity to reserve.", "#layby-sku-0", modal("[data-tour='layby-new']")),
      step("layby-save", "Save", "Confirm the layby and print the receipt.", MODAL_SAVE, modal("[data-tour='layby-new']", "top")),
    ],
  },
  {
    id: "customers",
    route: "/customers",
    exact: true,
    steps: [
      step("customer-new", "New customer", "Add a customer.", "[data-tour='customer-new']"),
      step("customer-name", "Name", "Enter the customer name.", "#create-customer-name", modal("[data-tour='customer-new']")),
      step("customer-save", "Save", "Save the customer.", MODAL_SAVE, modal("[data-tour='customer-new']", "top")),
    ],
  },
  {
    id: "returns",
    route: "/returns",
    exact: true,
    steps: [
      step("return-new", "New return", "Start a return.", "[data-tour='return-new']"),
      step("return-invoice", "Invoice", "Choose the invoice to return against.", "#return-invoice", modal("[data-tour='return-new']")),
      step("return-save", "Save", "Save the return.", MODAL_SAVE, modal("[data-tour='return-new']", "top")),
    ],
  },
  {
    id: "deliveries",
    route: "/deliveries",
    exact: true,
    steps: [
      step("delivery-new", "New delivery", "Start a delivery.", "[data-tour='delivery-new']"),
      step("delivery-source", "Source", "Choose the invoice, order, or layby to deliver.", "#delivery-source-type", modal("[data-tour='delivery-new']")),
      step("delivery-save", "Save", "Save the delivery.", MODAL_SAVE, modal("[data-tour='delivery-new']", "top")),
    ],
  },
  {
    id: "ledger",
    route: "/ledger",
    exact: true,
    steps: [
      step("ledger-new", "Add account", "Add a ledger account.", "[data-tour='ledger-new']"),
      step("ledger-code", "Code", "Enter the account code.", "#create-account-code", modal("[data-tour='ledger-new']")),
      step("ledger-save", "Save", "Save the account.", MODAL_SAVE, modal("[data-tour='ledger-new']", "top")),
    ],
  },
  {
    id: "journals",
    route: "/journals",
    exact: true,
    steps: [
      step("journal-new", "Create journal", "Create a journal.", "[data-tour='journal-new']"),
      step("journal-date", "Date", "Set the entry date and balance the lines.", "#journal-entry-date", modal("[data-tour='journal-new']")),
      step("journal-save", "Save", "Save the draft or post it.", MODAL_SAVE, modal("[data-tour='journal-new']", "top")),
    ],
  },
  {
    id: "invoices",
    route: "/invoices",
    exact: true,
    steps: [
      step("invoice-new", "Create invoice", "Create a tax invoice.", "[data-tour='invoice-new']"),
      step("invoice-customer", "Customer", "Choose the customer.", "#invoice-customer", modal("[data-tour='invoice-new']")),
      step("invoice-save", "Save", "Save the invoice.", MODAL_SAVE, modal("[data-tour='invoice-new']", "top")),
    ],
  },
  {
    id: "repeating-invoices",
    route: "/repeating-invoices",
    exact: true,
    steps: [
      step("repeating-new", "Create schedule", "Create a monthly invoice schedule.", "[data-tour='repeating-new']"),
      step("repeating-customer", "Customer", "Choose the customer.", "#repeating-customer", modal("[data-tour='repeating-new']")),
      step("repeating-save", "Save", "Save the schedule.", MODAL_SAVE, modal("[data-tour='repeating-new']", "top")),
    ],
  },
  {
    id: "credit-notes",
    route: "/credit-notes",
    exact: true,
    steps: [
      step("credit-note-new", "Issue credit note", "Issue a credit note against one invoice.", "[data-tour='credit-note-new']"),
      step("credit-note-invoice", "Invoice", "Choose the invoice to reverse.", "#credit-note-invoice", modal("[data-tour='credit-note-new']")),
      step("credit-note-save", "Save", "Issue the credit note.", MODAL_SAVE, modal("[data-tour='credit-note-new']", "top")),
    ],
  },
  {
    id: "bills",
    route: "/bills",
    exact: true,
    steps: [
      step("bill-new", "Create bill", "Create a supplier bill.", "[data-tour='bill-new']"),
      step("bill-supplier", "Supplier", "Choose the supplier.", "#bill-supplier", modal("[data-tour='bill-new']")),
      step("bill-save", "Save", "Save the bill.", MODAL_SAVE, modal("[data-tour='bill-new']", "top")),
    ],
  },
  {
    id: "payments",
    route: "/payments",
    exact: true,
    steps: [
      step("payments-list", "Payments", "Open an invoice or a bill to record a payment.", "[data-tour='payments-list']"),
    ],
  },
  {
    id: "bank",
    route: "/bank-reconciliation",
    exact: true,
    steps: [
      step("bank-account", "Account", "Choose the recon account.", "#bank-account-select"),
      step("bank-upload", "Import", "Import a bank CSV, then match each line.", "[data-tour='bank-upload']"),
    ],
  },
  {
    id: "reports",
    route: "/reports",
    exact: true,
    steps: [
      step("reports-as-of", "Dates", "Set the dates for the report.", "#as-of"),
      step("reports-refresh", "Refresh", "Refresh the figures, then export CSV.", "[data-tour='reports-refresh']"),
    ],
  },
  {
    id: "vat201",
    route: "/vat201",
    exact: true,
    steps: [
      step("vat-from", "Period", "Set the VAT period.", "#vat-period-from"),
      step("vat-create", "Create", "Create the draft return. Filing still happens in eFiling.", "[data-tour='vat-create']"),
    ],
  },
  {
    id: "books-periods",
    route: "/books-periods",
    exact: true,
    steps: [
      step("books-from", "Period", "Set the books period.", "#books-period-from"),
      step("books-create", "Create", "Create the period. Lock it to block journals on those dates.", "[data-tour='books-period-create']"),
    ],
  },
  {
    id: "users",
    route: "/users",
    exact: true,
    steps: [
      step("user-new", "Create user", "Create a back-office user.", "[data-tour='user-new']"),
      step("user-email", "Email", "Enter their email.", "#create-email", modal("[data-tour='user-new']")),
      step("user-save", "Save", "Save the user.", MODAL_SAVE, modal("[data-tour='user-new']", "top")),
    ],
  },
  {
    id: "roles",
    route: "/roles",
    exact: true,
    steps: [
      step("role-new", "Create role", "Create a custom role. Presets stay read-only.", "[data-tour='role-new']"),
      step("role-name", "Name", "Name the role.", "#create-role-name", modal("[data-tour='role-new']")),
      step("role-save", "Save", "Save the role, then assign it on Users.", MODAL_SAVE, modal("[data-tour='role-new']", "top")),
    ],
  },
  {
    id: "audit",
    route: "/audit",
    exact: true,
    steps: [
      step("audit-events", "Activity", "Open a row to see the document.", "[data-tour='audit-events']"),
    ],
  },
  {
    id: "profile",
    route: "/profile",
    exact: true,
    steps: [
      step("profile-name", "Your name", "This name shows in the header.", "#profile-display-name"),
      step("profile-save", "Save", "Save profile changes.", "[data-tour='profile-save']"),
      step("profile-tours", "Tours", "Replay this page, or start the full shop overview.", "[data-tour='profile-tours']"),
    ],
  },
  {
    id: "settings",
    route: "/settings",
    exact: true,
    steps: [
      step("settings-legal", "Legal name", "The legal name prints on tax invoices.", "#legal-name"),
      step("settings-save", "Save", "Save settings.", "[data-tour='settings-save']", { placement: "top" }),
    ],
  },
];

export const OVERVIEW_STEPS: TourStepDefinition[] = [
  step("overview-home", "Home", "Start stock, a count, an adjustment, import, a layby, or a return.", "[data-tour='home-actions']", { route: "/", exact: true }),
  step("overview-nav", "Sections", "Catalogue, stock, warehouse, till, sales, and books are in this rail.", ".firstout-side-nav", {
    route: "/",
    exact: true,
    placement: "right",
    isFixed: true,
    expandNav: true,
  }),
  step("overview-search", "Search", "Search SKUs, purchase orders, and invoices.", "[data-tour='header-search']", {
    route: "/",
    exact: true,
    isFixed: true,
  }),
  step("overview-catalogue", "Catalogue", "Create a SKU.", "[data-tour='catalogue-new']", { route: "/catalogue", exact: true }),
  step("overview-sku", "SKU", "Name it, set the category and retail price, then save.", "#new-sku-name", { route: "/catalogue/new", exact: true }),
  step("overview-count-location", "Stocktake", "Choose the location you are counting.", "#stocktake-location", { route: "/stocktakes", exact: true }),
  step("overview-count-start", "Start the count", "Start the count. That location stays locked until you post.", "[data-tour='stocktake-start']", { route: "/stocktakes", exact: true }),
  step("overview-po", "Purchase order", "Raise a purchase order.", "[data-tour='po-new']", { route: "/purchase-orders", exact: true }),
  step("overview-supplier", "Supplier", "Choose the supplier.", "#po-supplier", { route: "/purchase-orders", exact: true, ...modal("[data-tour='po-new']") }),
  step("overview-till", "Till", "Scan our barcode to sell.", "#till-scan", { route: "/till", exact: true }),
  step("overview-layby", "Layby", "Start a layby.", "[data-tour='layby-new']", { route: "/laybys", exact: true }),
  step("overview-layby-customer", "Layby customer", "Choose the customer who is reserving the item.", "#layby-customer", {
    route: "/laybys",
    exact: true,
    ...modal("[data-tour='layby-new']"),
  }),
  step("overview-layby-save", "Confirm layby", "Confirm the layby and print the receipt.", MODAL_SAVE, {
    route: "/laybys",
    exact: true,
    ...modal("[data-tour='layby-new']", "top"),
  }),
  step("overview-customer", "Customer", "Add a customer.", "[data-tour='customer-new']", { route: "/customers", exact: true }),
  step("overview-customer-name", "Customer name", "Enter the name, then save.", "#create-customer-name", {
    route: "/customers",
    exact: true,
    ...modal("[data-tour='customer-new']"),
  }),
  step("overview-invoice", "Invoice", "Create a tax invoice.", "[data-tour='invoice-new']", { route: "/invoices", exact: true }),
  step("overview-settings", "Settings", "The legal name prints on tax invoices.", "#legal-name", { route: "/settings", exact: true }),
  step("overview-replay", "Overview again", "This restarts the full shop tour. The question mark is only this page.", "[data-tour='header-overview-tour']", {
    placement: "bottom",
    isFixed: true,
  }),
];

export function pageTourForPath(pathname: string): PageTour | null {
  let best: PageTour | null = null;
  for (const tour of PAGE_TOURS) {
    const matches = tour.exact ? pathname === tour.route : pathname === tour.route || pathname.startsWith(`${tour.route}/`);
    if (!matches) {
      continue;
    }
    if (!best || tour.route.length > best.route.length) {
      best = tour;
    }
  }
  return best;
}
