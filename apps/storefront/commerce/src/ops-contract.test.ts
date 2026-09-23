import { medusaPrice, parseOpsProducts, shouldApplyRevision } from "./ops-contract";

const contract = {
  company_id: "6ba7b814-9dad-453f-9a1f-e66ece58b89b",
  products: [{
    source_sku_id: "e4653558-60c7-4be7-a416-76fc2c055b8f",
    sku: "ARC-001",
    name: "Arc sofa",
    price_minor_zar: 1150000,
    available_quantity: 2,
    revision: "2026-09-22T09:14:32.000001",
    observed_at: "2026-09-22T09:14:32.000001",
  }],
};

test("validates a provider-neutral private product snapshot", () => {
  expect(parseOpsProducts(contract, contract.company_id).products[0].sku).toBe("ARC-001");
  expect(() => parseOpsProducts(contract, "912f8c83-777f-4485-9ddd-f1d709db18f6")).toThrow();
  expect(() => parseOpsProducts({ ...contract, products: [...contract.products, contract.products[0]] }, contract.company_id)).toThrow();
  expect(() => parseOpsProducts({ ...contract, products: [{ ...contract.products[0], supplier_ref: "private" }] }, contract.company_id)).toThrow();
});

test("converts exact ZAR cents to Medusa v2 major units", () => {
  expect(medusaPrice(1150000)).toBe(11500);
  expect(medusaPrice(115001)).toBe(1150.01);
  expect(() => medusaPrice(-1)).toThrow();
});

test("applies only newer source observations", () => {
  expect(shouldApplyRevision("2026-09-22T09:15:00.000000", "2026-09-22T09:14:32.000001")).toBe(true);
  expect(shouldApplyRevision("2026-09-22T09:14:32.000001", "2026-09-22T09:14:32.000001")).toBe(false);
  expect(shouldApplyRevision("2026-09-22T09:14:00.000000", "2026-09-22T09:14:32.000001")).toBe(false);
});
