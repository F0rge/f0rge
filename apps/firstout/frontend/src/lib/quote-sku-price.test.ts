import { describe, expect, it } from "vitest";

import type { CustomerCrm, PriceList, Sku } from "@/lib/api";

import {
  canEditQuoteDiscount,
  canOverrideQuoteUnitPrice,
  formatQuoteSkuOption,
  formatUnitExVatInput,
  isCin7GeneratedPriceList,
  quoteLineExVat,
  quoteLineSuspectWarning,
  quoteSkuMatchesQuery,
  quoteSkuUnitExVat,
  quoteUnitPriceHelper,
  RESTRICTED_SUSPECT_PRICE_WARNING,
  suspectUnitPriceWarning,
} from "./quote-sku-price";

function sku(overrides: Partial<Sku> = {}): Sku {
  return {
    id: "sku-1",
    our_ref: "PG-TABLE",
    our_barcode: "PG-TABLE-BAR",
    name: "Dining table",
    design: "design",
    fabric: "fabric",
    category: null,
    supplier_ref: null,
    preferred_supplier_id: null,
    preferred_supplier_name: null,
    lead_time_days: null,
    made_to_order_capacity: null,
    made_to_order_lead_time_min_days: null,
    made_to_order_lead_time_max_days: null,
    made_to_order_expires_at: null,
    made_to_order_offer_id: null,
    reorder_min: null,
    last_landed_cost_zar: null,
    photo_storage_key: null,
    stockist_ex_vat: null,
    stockist_inc_vat: null,
    wholesale_ex_vat: "800.00",
    wholesale_inc_vat: "920.00",
    decorator_ex_vat: null,
    decorator_inc_vat: null,
    retail_ex_vat: "1000.00",
    retail_inc_vat: "1150.00",
    carton_count: 1,
    is_kit: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function customer(overrides: Partial<CustomerCrm> = {}): CustomerCrm {
  return {
    id: "cust-1",
    name: "Trade House",
    email: null,
    phone: null,
    vat_number: null,
    billing_address: null,
    customer_type: "trade",
    price_classification: "Wholesale",
    price_tier: "ignored-tier",
    open_invoices_count: 0,
    open_invoices_zar: "0.00",
    overdue_invoices_count: 0,
    overdue_invoices_zar: "0.00",
    active_laybys_count: 0,
    active_laybys_zar: "0.00",
    last_purchase_date: null,
    credit_limit: null,
    on_hold: false,
    on_hold_reason: null,
    payment_terms_days: null,
    price_list_id: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
    payment_reminders_opt_out: overrides.payment_reminders_opt_out ?? false,
  };
}

const decoratorList: PriceList = {
  id: "list-1",
  name: "Decorator",
  items: [{ sku_id: "sku-1", our_ref: "PG-TABLE", unit_ex_vat: "900.00" }],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("canOverrideQuoteUnitPrice", () => {
  it("allows only the owner role to edit a quote unit price", () => {
    expect(canOverrideQuoteUnitPrice("owner")).toBe(true);
    expect(canOverrideQuoteUnitPrice("buyer")).toBe(false);
    expect(canOverrideQuoteUnitPrice("warehouse")).toBe(false);
    expect(canOverrideQuoteUnitPrice("till")).toBe(false);
    expect(canOverrideQuoteUnitPrice("books")).toBe(false);
    expect(canOverrideQuoteUnitPrice("custom-sales")).toBe(false);
    expect(canOverrideQuoteUnitPrice(null)).toBe(false);
  });
});

describe("canEditQuoteDiscount", () => {
  it("allows owner, till, and warehouse to edit a line discount", () => {
    expect(canEditQuoteDiscount("owner")).toBe(true);
    expect(canEditQuoteDiscount("till")).toBe(true);
    expect(canEditQuoteDiscount("warehouse")).toBe(true);
    expect(canEditQuoteDiscount("buyer")).toBe(false);
    expect(canEditQuoteDiscount("books")).toBe(false);
    expect(canEditQuoteDiscount("custom-sales")).toBe(false);
    expect(canEditQuoteDiscount(undefined)).toBe(false);
  });
});

describe("quoteLineExVat", () => {
  it("takes a percent off the line total and leaves the unit price unchanged", () => {
    expect(quoteLineExVat(1, "1000.00", "10")).toBe(900);
    expect(quoteLineExVat(2, "1000.00", "10")).toBe(1800);
    expect(quoteLineExVat(1, "1000.00", "0")).toBe(1000);
    expect(quoteLineExVat(1, "1000.00", "")).toBe(1000);
  });
});

describe("quoteSkuUnitExVat", () => {
  it("uses retail ex VAT when no customer is chosen", () => {
    const priced = quoteSkuUnitExVat(sku(), null, [decoratorList]);
    expect(priced).toEqual({
      unitExVat: 1000,
      source: "retail",
      priceListName: null,
      warning: null,
      pricesIncludeVat: true,
      belowAverageCost: false,
    });
  });

  it("uses wholesale ex VAT for a wholesale customer", () => {
    const priced = quoteSkuUnitExVat(sku(), customer(), []);
    expect(priced.source).toBe("wholesale");
    expect(priced.unitExVat).toBe(800);
    expect(priced.pricesIncludeVat).toBe(false);
  });

  it("uses the stockist and decorator columns for those classifications", () => {
    const item = sku({ stockist_ex_vat: "700.00", decorator_ex_vat: "650.00" });
    expect(
      quoteSkuUnitExVat(item, customer({ price_classification: "Stockist" }), []),
    ).toMatchObject({ unitExVat: 700, source: "stockist", pricesIncludeVat: false });
    expect(
      quoteSkuUnitExVat(item, customer({ price_classification: "Decorator" }), []),
    ).toMatchObject({ unitExVat: 650, source: "decorator", pricesIncludeVat: false });
  });

  it("uses retail ex VAT for a retail customer even when wholesale is set", () => {
    const priced = quoteSkuUnitExVat(
      sku(),
      customer({ customer_type: "retail", price_classification: "Retail" }),
      [],
    );
    expect(priced).toMatchObject({ unitExVat: 1000, source: "retail", pricesIncludeVat: true });
  });

  it("ignores the price_tier label", () => {
    const priced = quoteSkuUnitExVat(
      sku(),
      customer({
        customer_type: "retail",
        price_classification: "Retail",
        price_tier: "Wholesale",
      }),
      [],
    );
    expect(priced.source).toBe("retail");
  });

  it("prefers the customer's price list over the classification tier", () => {
    const priced = quoteSkuUnitExVat(
      sku(),
      customer({ price_list_id: "list-1" }),
      [decoratorList],
    );
    expect(priced).toEqual({
      unitExVat: 900,
      source: "price_list",
      priceListName: "Decorator",
      warning: null,
      pricesIncludeVat: false,
      belowAverageCost: false,
    });
  });

  it("ignores a Cin7 Tier 4 list and keeps the classification price", () => {
    const cin7Tier4: PriceList = {
      id: "cin7-tier-4",
      name: "Cin7 Tier 4",
      items: [{ sku_id: "sku-1", our_ref: "PG-TABLE", unit_ex_vat: "1150.00" }],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    const priced = quoteSkuUnitExVat(
      sku(),
      customer({
        customer_type: "retail",
        price_classification: "Retail",
        price_list_id: "cin7-tier-4",
      }),
      [cin7Tier4, decoratorList],
    );
    expect(priced).toMatchObject({
      unitExVat: 1000,
      source: "retail",
      priceListName: null,
      pricesIncludeVat: true,
    });
    expect(isCin7GeneratedPriceList("Cin7 Retail")).toBe(true);
    expect(isCin7GeneratedPriceList("Cin7 Tier 10")).toBe(true);
    expect(isCin7GeneratedPriceList("Decorator")).toBe(false);
  });

  it("uses a price list for a retail customer and still shows prices including VAT", () => {
    const priced = quoteSkuUnitExVat(
      sku(),
      customer({
        customer_type: "retail",
        price_classification: "Retail",
        price_list_id: "list-1",
      }),
      [decoratorList],
    );
    expect(priced.source).toBe("price_list");
    expect(priced.unitExVat).toBe(900);
    expect(priced.pricesIncludeVat).toBe(true);
  });

  it("falls through to wholesale when the list has no row for the SKU", () => {
    const priced = quoteSkuUnitExVat(
      sku({ id: "sku-2" }),
      customer({ price_list_id: "list-1" }),
      [decoratorList],
    );
    expect(priced.source).toBe("wholesale");
    expect(priced.unitExVat).toBe(800);
  });

  it("falls back to retail with a warning when the classification price is missing", () => {
    const priced = quoteSkuUnitExVat(sku({ wholesale_ex_vat: null }), customer(), []);
    expect(priced).toMatchObject({
      unitExVat: 1000,
      source: "retail_fallback",
      pricesIncludeVat: false,
    });
    expect(priced.warning).toContain("Wholesale price is missing");
    expect(priced.warning).toContain("Retail");
  });

  it("treats zero and blank prices as missing", () => {
    const priced = quoteSkuUnitExVat(
      sku({ retail_ex_vat: "0.00", wholesale_ex_vat: "" }),
      null,
      [],
    );
    expect(priced).toEqual({
      unitExVat: null,
      source: "missing",
      priceListName: null,
      warning: null,
      pricesIncludeVat: true,
      belowAverageCost: false,
    });
  });
});

describe("formatQuoteSkuOption", () => {
  it("shows the retail price including VAT when there is no customer", () => {
    const item = sku();
    const label = formatQuoteSkuOption(item, null, []);
    expect(label).toBe("PG-TABLE — Dining table · R 1150.00 Retail incl. VAT");
    expect(quoteSkuMatchesQuery(item, "dining", label)).toBe(true);
    expect(quoteSkuMatchesQuery(item, label, label)).toBe(true);
    expect(quoteSkuMatchesQuery(item, "PG-TABLE-BAR", label)).toBe(true);
    expect(quoteSkuMatchesQuery(item, "missing-sku", label)).toBe(false);
  });

  it("leads with the list price", () => {
    const label = formatQuoteSkuOption(sku(), customer({ price_list_id: "list-1" }), [
      decoratorList,
    ]);
    expect(label).toContain("R 900.00 list excl. VAT");
  });

  it("leads with wholesale excl. VAT for a wholesale customer", () => {
    const label = formatQuoteSkuOption(sku(), customer(), []);
    expect(label).toBe("PG-TABLE — Dining table · R 800.00 Wholesale excl. VAT");
  });
});

describe("quote unit field copy", () => {
  it("formats the auto-filled ex VAT amount and names the source", () => {
    expect(formatUnitExVatInput(900)).toBe("900.00");
    expect(formatUnitExVatInput(null)).toBe("");
    expect(quoteUnitPriceHelper(
      {
        unitExVat: 900,
        source: "price_list",
        priceListName: "Decorator",
        warning: null,
        pricesIncludeVat: false,
        belowAverageCost: false,
      },
      true,
    )).toBe("Price list Decorator overrides the classification · excl. VAT");
    expect(quoteUnitPriceHelper(
      {
        unitExVat: 1000,
        source: "retail",
        priceListName: null,
        warning: null,
        pricesIncludeVat: true,
        belowAverageCost: false,
      },
      false,
    )).toBe("Retail · incl. VAT (no customer)");
  });
});

describe("suspectUnitPriceWarning", () => {
  const healthy = {
    averageUnitCostZar: "400.00" as string | null,
    catalogueBelowCost: false,
    unitMatchesCatalogue: true,
    canViewCost: true,
  };

  it("warns when the unit is R1.00 ex VAT or less, including a R1.00 incl. VAT placeholder", () => {
    expect(suspectUnitPriceWarning({ ...healthy, unitExVat: 1, averageUnitCostZar: null })).toBe(
      "Unit price R1.00 excl. VAT is R1.00 excl. VAT or below (R1.15 incl. VAT or less). Check this price.",
    );
    expect(
      suspectUnitPriceWarning({
        ...healthy,
        unitExVat: 0.87,
        averageUnitCostZar: null,
        pricesIncludeVat: true,
      }),
    ).toBe(
      "Unit price R1.00 incl. VAT (R0.87 excl.) is R1.00 excl. VAT or below (R1.15 incl. VAT or less). Check this price.",
    );
    const atCost = suspectUnitPriceWarning({ ...healthy, unitExVat: 1, averageUnitCostZar: "1.00" });
    expect(atCost).toContain("R1.00 excl. VAT or below");
    expect(atCost).not.toContain("below average cost");
  });

  it("warns when the unit is below average cost and shows the cost to someone who can see it", () => {
    const message = suspectUnitPriceWarning({
      ...healthy,
      unitExVat: 400,
      averageUnitCostZar: "1500.50",
      unitMatchesCatalogue: false,
    });
    expect(message).toBe(
      "Unit price R400.00 excl. VAT is below average cost R1500.50 excl. VAT.",
    );
  });

  it("quotes a retail line in the incl. VAT amount the line shows", () => {
    expect(
      suspectUnitPriceWarning({
        ...healthy,
        unitExVat: 400,
        averageUnitCostZar: "1500.00",
        pricesIncludeVat: true,
      }),
    ).toBe(
      "Unit price R460.00 incl. VAT (R400.00 excl.) is below average cost R1500.00 excl. VAT.",
    );
  });

  it("stays quiet for a normal price", () => {
    expect(suspectUnitPriceWarning({ ...healthy, unitExVat: 800 })).toBeNull();
    expect(suspectUnitPriceWarning({ ...healthy, unitExVat: 1.01, averageUnitCostZar: "0.50" })).toBeNull();
  });

  it("does not reveal the cost figure when the viewer cannot see costs", () => {
    const message = suspectUnitPriceWarning({
      unitExVat: 400,
      averageUnitCostZar: "1500.00",
      catalogueBelowCost: true,
      unitMatchesCatalogue: true,
      canViewCost: false,
    });
    expect(message).toBe(RESTRICTED_SUSPECT_PRICE_WARNING);
    expect(message).not.toContain("1500");
    expect(
      suspectUnitPriceWarning({
        unitExVat: 400,
        averageUnitCostZar: "1500.00",
        catalogueBelowCost: false,
        unitMatchesCatalogue: false,
        canViewCost: false,
      }),
    ).toBeNull();
  });

  it("still warns when a manual unit matches the rule", () => {
    const message = quoteLineSuspectWarning(
      "1.00",
      { average_unit_cost_zar: "900.00" },
      {
        unitExVat: 800,
        source: "wholesale",
        priceListName: null,
        warning: null,
        pricesIncludeVat: false,
        belowAverageCost: false,
      },
      true,
    );
    expect(message).toContain("Unit price R1.00 excl. VAT");
    expect(message).toContain("R900.00 excl. VAT");
    expect(
      quoteLineSuspectWarning(
        "400.00",
        { average_unit_cost_zar: "1500.00" },
        {
          unitExVat: 800,
          source: "retail",
          priceListName: null,
          warning: null,
          pricesIncludeVat: true,
          belowAverageCost: false,
        },
        true,
        true,
      ),
    ).toBe(
      "Unit price R460.00 incl. VAT (R400.00 excl.) is below average cost R1500.00 excl. VAT.",
    );
  });

  it("marks the stockist tier and a price-list row that are below cost", () => {
    const item = sku({ stockist_ex_vat: "50.00", stockist_below_cost: true });
    expect(
      quoteSkuUnitExVat(item, customer({ price_classification: "Stockist" }), []).belowAverageCost,
    ).toBe(true);
    const list: PriceList = {
      ...decoratorList,
      items: [{ sku_id: "sku-1", our_ref: "PG-TABLE", unit_ex_vat: "900.00", below_average_cost: true }],
    };
    expect(
      quoteSkuUnitExVat(sku(), customer({ price_list_id: "list-1" }), [list]).belowAverageCost,
    ).toBe(true);
  });
});
