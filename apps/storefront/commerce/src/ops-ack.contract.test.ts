import { parseOpsProducts, pendingCommitments, projectAvailableQuantity, shouldApplyRevision } from "./ops-contract";

const companyId = "6ba7b814-9dad-453f-9a1f-e66ece58b89b";
const sourceSkuId = "e4653558-60c7-4be7-a416-76fc2c055b8f";
const commitmentId = "line_746_paid_1";

const pending = {
  company_id: companyId,
  products: [{
    source_sku_id: sourceSkuId,
    product_group_id: null,
    product_title: null,
    options: {},
    sku: "ARC-001",
    name: "Arc sofa",
    price_minor_zar: 1150000,
    available_quantity: 2,
    revision: "2026-09-27T08:00:00.000001Z",
    observed_at: "2026-09-27T08:00:00.000001Z",
    acknowledged_commitment_ids: [],
    made_to_order_offer: null,
  }],
};

const acknowledged = {
  company_id: companyId,
  products: [{
    ...pending.products[0],
    available_quantity: 1,
    revision: "2026-09-27T08:01:00.000001Z",
    observed_at: "2026-09-27T08:01:00.000001Z",
    acknowledged_commitment_ids: [commitmentId],
  }],
};

test("accepts pending and acknowledged Ops snapshots while ignoring reordered observations", () => {
  const before = parseOpsProducts(pending, companyId).products[0];
  const after = parseOpsProducts(acknowledged, companyId).products[0];
  expect(before.acknowledged_commitment_ids).toEqual([]);
  expect(after.acknowledged_commitment_ids).toEqual([commitmentId]);
  expect(shouldApplyRevision(after.revision, before.revision)).toBe(true);
  expect(shouldApplyRevision(before.revision, after.revision)).toBe(false);
  expect(shouldApplyRevision(after.revision, after.revision)).toBe(false);
  const paidLine = [{ commitment_id: commitmentId, source_sku_id: sourceSkuId, quantity: 1 }];
  expect(projectAvailableQuantity(before, paidLine)).toBe(1);
  expect(projectAvailableQuantity(before, pendingCommitments({ pending_paid_commitments: paidLine }))).toBe(1);
  expect(projectAvailableQuantity(after, paidLine)).toBe(1);
  expect(projectAvailableQuantity(after, [{ ...paidLine[0], acknowledged_revision: after.revision }])).toBe(1);
  expect(() => projectAvailableQuantity(before, [{ ...paidLine[0], acknowledged_revision: after.revision }])).toThrow();
  expect(() => pendingCommitments({ pending_paid_commitments: [paidLine[0], paidLine[0]] })).toThrow();
});
