import { describe, expect, it } from "vitest";
import type { MadeToOrderOffer, MedusaVariant, StoreProduct } from "./medusa";
import { availabilityLabel, offerState, optionsLabel, pieceAvailability, pieceDimensions, pieceMaterial, sharedDimensions, sizeLabel } from "./piece-spec";

const now = Date.parse("2026-11-20T08:00:00Z");
const offer = (overrides: Partial<MadeToOrderOffer> = {}): MadeToOrderOffer => ({
  id: "offer", capacity: 5, remaining_capacity: 2, min_lead_time_days: 14, max_lead_time_days: 21,
  expires_at: "2026-12-01T00:00:00Z", observed_at: "2026-11-20T07:58:00Z", ...overrides,
});
const variant = (overrides: Partial<MedusaVariant> = {}): MedusaVariant => ({ id: "v", sku: "S", inventory_quantity: 0, ...overrides });
const product = (overrides: Partial<StoreProduct> = {}): StoreProduct => ({ id: "p", handle: "h", title: "Piece", description: null, variants: [], ...overrides });

describe("piece availability", () => {
  it("reports stock first", () => {
    const result = pieceAvailability([variant(), variant({ inventory_quantity: 3 })], now);
    expect(availabilityLabel(result)).toBe("In stock");
  });

  it("shows the real lead-time window of a fresh made-to-order offer", () => {
    const result = pieceAvailability([variant({ metadata: { made_to_order_offer: offer() } })], now);
    expect(result).toEqual({ kind: "made_to_order", minDays: 14, maxDays: 21 });
    expect(availabilityLabel(result)).toBe("Made to order · 14–21 days");
  });

  it("never offers a stale, expired or exhausted offer", () => {
    expect(offerState(offer({ observed_at: "2026-11-20T07:50:00Z" }), now)).toBe("stale");
    expect(offerState(offer({ observed_at: null }), now)).toBe("stale");
    expect(offerState(offer({ expires_at: "2026-11-19T00:00:00Z" }), now)).toBe("exhausted");
    expect(offerState(offer({ remaining_capacity: 0 }), now)).toBe("exhausted");
    expect(availabilityLabel(pieceAvailability([variant({ metadata: { made_to_order_offer: offer({ observed_at: "2026-11-20T07:50:00Z" }) } })], now))).toBe("Availability being confirmed");
    expect(availabilityLabel(pieceAvailability([variant({ metadata: { made_to_order_offer: offer({ remaining_capacity: 0 }) } })], now))).toBe("Currently unavailable");
    expect(availabilityLabel(pieceAvailability([variant()], now))).toBe("Currently unavailable");
  });

  it("rejects an offer observed in the future beyond the clock-skew allowance", () => {
    expect(offerState(offer({ observed_at: "2026-11-20T08:00:30Z" }), now)).toBe("available");
    expect(offerState(offer({ observed_at: "2026-11-20T08:05:00Z" }), now)).toBe("stale");
  });

  it("combines live offers into the widest window and labels a single-day window once", () => {
    const result = pieceAvailability([
      variant({ metadata: { made_to_order_offer: offer({ min_lead_time_days: 10, max_lead_time_days: 14 }) } }),
      variant({ metadata: { made_to_order_offer: offer({ min_lead_time_days: 21, max_lead_time_days: 35 }) } }),
      variant({ metadata: { made_to_order_offer: offer({ min_lead_time_days: 2, max_lead_time_days: 60, remaining_capacity: 0 }) } }),
    ], now);
    expect(availabilityLabel(result)).toBe("Made to order · 10–35 days");
    expect(availabilityLabel({ kind: "made_to_order", minDays: 7, maxDays: 7 })).toBe("Made to order · 7 days");
  });

  it("reports a mix of stale and exhausted offers as being confirmed, not purchasable", () => {
    const result = pieceAvailability([
      variant({ metadata: { made_to_order_offer: offer({ remaining_capacity: 0 }) } }),
      variant({ metadata: { made_to_order_offer: offer({ observed_at: null }) } }),
    ], now);
    expect(result).toEqual({ kind: "unconfirmed" });
  });
});

describe("piece dimensions", () => {
  it("falls back from a missing variant value to the product's, as the product page does", () => {
    const piece = product({ length: 200, width: 90, height: 80, metadata: { dimension_unit: "mm" } });
    expect(pieceDimensions(piece, variant({ width: 95 }))).toEqual({ length: 200, width: 95, height: 80, unit: "mm" });
    // A recorded zero is not a missing value, so it hides the dimension rather than falling back.
    expect(pieceDimensions(piece, variant({ height: 0 })).height).toBeNull();
    expect(pieceDimensions(product(), variant())).toEqual({ length: null, width: null, height: null, unit: "" });
  });

  it("omits the size when any dimension is missing", () => {
    const dims = sharedDimensions(product({ width: 90, height: 80, metadata: { dimension_unit: "cm" } }), [variant()]);
    expect(dims).toMatchObject({ length: null, width: 90, height: 80, unit: "cm" });
    expect(sizeLabel(dims)).toBeNull();
  });

  it("states the size when every variant agrees, and drops a value that differs", () => {
    const piece = product({ length: 200, width: 90, height: 80, metadata: { dimension_unit: "cm" } });
    expect(sizeLabel(sharedDimensions(piece, [variant(), variant()]))).toBe("L 200 × W 90 × H 80 cm");
    expect(sharedDimensions(piece, [variant(), variant({ length: 240 })]).length).toBeNull();
  });
});

describe("tile options and material", () => {
  const fill = { id: "fill", title: "Fill", values: [{ id: "s", value: "Soft" }, { id: "f", value: "Firm" }] };
  const soft = variant({ id: "soft", options: [{ id: "o1", value: "Soft", option_id: "fill" }], material: "Linen" });
  const firm = variant({ id: "firm", options: [{ id: "o2", value: "Firm", option_id: "fill" }], material: "Linen" });
  const piece = product({ options: [fill], variants: [soft, firm], material: "Fabric" });

  it("lists only the option values present in the listed variants", () => {
    expect(optionsLabel(piece, [soft, firm])).toBe("Fill: Soft / Firm");
    expect(optionsLabel(piece, [firm])).toBe("Fill: Firm");
    expect(optionsLabel(product({ options: [fill], variants: [soft] }), [soft])).toBeNull();
  });

  it("shows a material only when every listed variant resolves to the same one", () => {
    expect(pieceMaterial(piece, [soft, firm])).toBe("Linen");
    expect(pieceMaterial(piece, [soft, variant({ material: "Leather" })])).toBeNull();
    expect(pieceMaterial(piece, [variant(), variant()])).toBe("Fabric");
    expect(pieceMaterial(piece, [soft, variant()])).toBeNull();
    expect(pieceMaterial(product(), [variant()])).toBeNull();
  });
});
