import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { POST } from "./route";

function call(body: Record<string, unknown>) {
  const headers: Record<string, string> = {};
  const res = {
    setHeader(name: string, value: string) { headers[name] = value; },
    statusCode: 200,
    body: undefined as unknown,
    status(code: number) { this.statusCode = code; return this; },
    json(value: unknown) { this.body = value; return this; },
  };
  return { req: { body } as MedusaRequest, res: res as unknown as MedusaResponse, raw: res, headers };
}

test("test-route alerts redact customer context and distinguish aged from terminal failures", async () => {
  const aged = call({
    kind: "missing_operational_paid_order",
    status: "retry_wait",
    created_at: "2026-10-03T11:50:00.000Z",
    correlation_id: "storefront:order:seed-missing-handoff",
    customer_email: "payer@example.test",
    payment_reference: "secret-ref",
    last_error: "ops_unavailable",
  });
  await POST(aged.req, aged.res);
  const agedBody = aged.raw.body as { queue_class: string; context: Record<string, unknown> };
  expect(aged.raw.statusCode).toBe(200);
  expect(agedBody.queue_class).toBe("aged");
  expect(JSON.stringify(agedBody.context)).not.toContain("payer@example.test");

  const terminal = call({
    kind: "capacity_conflict",
    status: "failed",
    created_at: new Date().toISOString(),
    retryable: false,
    correlation_id: "storefront:capacity:seed-conflict",
  });
  await POST(terminal.req, terminal.res);
  expect((terminal.raw.body as { queue_class: string }).queue_class).toBe("terminal");
});
