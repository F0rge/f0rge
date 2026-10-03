import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { classifyHandoffQueue, redactAlertContext } from "../../../../storefront-commerce-exceptions";

export async function POST(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  res.setHeader("Cache-Control", "private, no-store, max-age=0");
  const body = (req.body && typeof req.body === "object" ? req.body : {}) as Record<string, unknown>;
  const createdAt = typeof body.created_at === "string" ? Date.parse(body.created_at) : Date.now() - 10 * 60 * 1000;
  const status = typeof body.status === "string" ? body.status : "retry_wait";
  const queueClass = classifyHandoffQueue({
    status,
    createdAtMs: Number.isFinite(createdAt) ? createdAt : Date.now(),
    nowMs: Date.now(),
    retryable: body.retryable !== false && status !== "failed",
  });
  const context = redactAlertContext({
    kind: typeof body.kind === "string" ? body.kind : "missing_operational_paid_order",
    status,
    correlation_id: typeof body.correlation_id === "string" ? body.correlation_id : "storefront:order:unspecified",
    last_error: typeof body.last_error === "string" ? body.last_error : "ops_unavailable",
    customer_email: body.customer_email,
    payment_reference: body.payment_reference,
    amount_minor: body.amount_minor,
  });
  res.status(200).json({
    delivered: true,
    queue_class: queueClass,
    context,
    paid_recovery_retained: true,
  });
}
