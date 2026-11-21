import { createHmac } from "node:crypto";
import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { POST } from "./route";
import { findPaystackAttemptByReference } from "../../../paystack-payment-store";
import { verifyAndProcessPaystackCharge } from "../../../paystack-webhook-processing";
import { reconcilePaystackRefundsForCapture } from "../../../storefront-paystack-refunds";

jest.mock("../../../runtime-safety", () => ({ isHostedRuntime: () => false }));
jest.mock("../../../paystack-payment-store", () => ({ findPaystackAttemptByReference: jest.fn() }));
jest.mock("../../../paystack-webhook-processing", () => ({ verifyAndProcessPaystackCharge: jest.fn() }));
jest.mock("../../../storefront-paystack-refunds", () => ({ reconcilePaystackRefundsForCapture: jest.fn() }));

const secret = "whsec_route_test";
const attempt = { id: "spay_1", reference: "dk_reference_route", payment_session_id: "payses_1" };
const env = { PAYSTACK_SECRET_KEY: process.env.PAYSTACK_SECRET_KEY, PAYSTACK_WEBHOOK_SECRET: process.env.PAYSTACK_WEBHOOK_SECRET };

function signed(body: string, t = Math.floor(Date.now() / 1000)): string {
  return `t=${t},v1=whk_test:${createHmac("sha512", secret).update(`${t}.`).update(body).digest("hex")}`;
}

async function call(body: string, signature?: string): Promise<{ status: number; body: Record<string, unknown> }> {
  const result = { status: 0, body: {} as Record<string, unknown> };
  const res = {
    setHeader: jest.fn(),
    status(code: number) { result.status = code; return this; },
    json(value: Record<string, unknown>) { result.body = value; return this; },
  } as unknown as MedusaResponse;
  const req = {
    rawBody: Buffer.from(body),
    headers: signature ? { "paystack-signature": signature } : {},
    scope: { resolve: () => ({}) },
  } as unknown as MedusaRequest;
  await POST(req, res);
  return result;
}

const charge = JSON.stringify({ event: "charge.success", data: { reference: attempt.reference, amount: 1 } });

beforeEach(() => {
  jest.clearAllMocks();
  process.env.PAYSTACK_SECRET_KEY = "sk_test_route";
  process.env.PAYSTACK_WEBHOOK_SECRET = secret;
  jest.mocked(findPaystackAttemptByReference).mockResolvedValue(attempt as never);
  jest.mocked(verifyAndProcessPaystackCharge).mockResolvedValue("processed");
  jest.mocked(reconcilePaystackRefundsForCapture).mockResolvedValue(1);
});

afterAll(() => {
  for (const [key, value] of Object.entries(env)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
});

test("is unavailable while Paystack is not configured", async () => {
  delete process.env.PAYSTACK_SECRET_KEY;
  delete process.env.PAYSTACK_WEBHOOK_SECRET;
  expect((await call(charge, signed(charge))).status).toBe(404);
  expect(verifyAndProcessPaystackCharge).not.toHaveBeenCalled();
});

test("rejects missing, wrong, future, and stale signatures before reading the database", async () => {
  const now = Math.floor(Date.now() / 1000);
  for (const signature of [undefined, `t=${now},v1=whk_test:${"0".repeat(128)}`, signed(charge, now + 301), signed(charge, now - 301)]) {
    expect((await call(charge, signature)).status).toBe(401);
  }
  expect(findPaystackAttemptByReference).not.toHaveBeenCalled();
});

test("rejects a signed but malformed body", async () => {
  for (const body of ["not json", JSON.stringify({ event: "charge.success", data: { reference: "x" } })]) {
    expect((await call(body, signed(body))).status).toBe(400);
  }
});

test("acknowledges events that are not ours without processing them", async () => {
  jest.mocked(findPaystackAttemptByReference).mockResolvedValue(undefined);
  expect(await call(charge, signed(charge))).toEqual({ status: 200, body: { received: true, ignored: true } });
  const other = JSON.stringify({ event: "transfer.success", data: {} });
  expect((await call(other, signed(other))).status).toBe(200);
  expect(verifyAndProcessPaystackCharge).not.toHaveBeenCalled();
});

test("re-reads a charge or the charge's refunds from Paystack for our references", async () => {
  expect((await call(charge, signed(charge))).status).toBe(200);
  expect(verifyAndProcessPaystackCharge).toHaveBeenCalledWith(expect.anything(), attempt, "webhook", expect.stringMatching(/^t=/));
  const refund = JSON.stringify({ event: "refund.processed", data: { transaction_reference: attempt.reference, amount: "5000" } });
  expect((await call(refund, signed(refund))).status).toBe(200);
  expect(reconcilePaystackRefundsForCapture).toHaveBeenCalledWith(expect.anything(), attempt.reference, "webhook", fetch, expect.any(String));
});

test("defers with 503 so Paystack redelivers when the authoritative read fails", async () => {
  jest.mocked(verifyAndProcessPaystackCharge).mockRejectedValueOnce(new Error("paystack_verify_http_502"));
  expect((await call(charge, signed(charge))).status).toBe(503);
  jest.mocked(verifyAndProcessPaystackCharge).mockResolvedValueOnce("not_found");
  expect((await call(charge, signed(charge))).status).toBe(503);
  const refund = JSON.stringify({ event: "refund.failed", data: { transaction_reference: attempt.reference } });
  jest.mocked(reconcilePaystackRefundsForCapture).mockRejectedValueOnce(new Error("paystack_refund_list_http_500"));
  expect((await call(refund, signed(refund))).status).toBe(503);
});
