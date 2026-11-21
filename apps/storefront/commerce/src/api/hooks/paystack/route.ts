import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { parsePaystackWebhook, verifyPaystackWebhookSignature } from "../../../paystack-checkout";
import { paystackPaymentConfig } from "../../../paystack-payment-config";
import { findPaystackAttemptByReference } from "../../../paystack-payment-store";
import { verifyAndProcessPaystackCharge } from "../../../paystack-webhook-processing";
import { reconcilePaystackRefundsForCapture } from "../../../storefront-paystack-refunds";

function rawBody(value: unknown): Buffer | undefined {
  if (Buffer.isBuffer(value)) return value;
  if (typeof value === "string") return Buffer.from(value, "utf8");
  if (value instanceof Uint8Array) return Buffer.from(value);
  return undefined;
}

/**
 * Paystack webhook. The signed body is only a trigger: the charge or refund
 * state is re-read from Paystack's authenticated API before anything changes.
 * Paystack retries non-2xx responses (live: every 3 minutes x4, then hourly
 * for 72 hours), and identical normalized facts are deduplicated in the inbox.
 */
export async function POST(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  res.setHeader("Cache-Control", "no-store");
  const config = paystackPaymentConfig();
  if (!config) {
    res.status(404).json({ message: "Paystack webhook is unavailable" });
    return;
  }

  const body = rawBody(req.rawBody);
  const signature = req.headers["paystack-signature"];
  if (typeof signature !== "string" || !verifyPaystackWebhookSignature({ secret: config.webhookSecret, header: signature, rawBody: body })) {
    res.status(401).json({ message: "Paystack webhook signature is invalid" });
    return;
  }
  const trigger = parsePaystackWebhook(body!);
  if (!trigger) {
    res.status(400).json({ message: "Paystack webhook event is invalid" });
    return;
  }
  if (trigger.event === "ignored") {
    res.status(200).json({ received: true });
    return;
  }

  const db = req.scope.resolve(ContainerRegistrationKeys.PG_CONNECTION) as Knex;
  try {
    const attempt = await findPaystackAttemptByReference(db, trigger.reference);
    // Another sales channel on the same Paystack account; acknowledge so it is not retried.
    if (!attempt) {
      res.status(200).json({ received: true, ignored: true });
      return;
    }
    if (trigger.event === "charge.success") {
      const outcome = await verifyAndProcessPaystackCharge(req.scope, attempt, "webhook", signature);
      if (outcome === "not_found") throw new Error("paystack_transaction_not_found");
      res.status(200).json({ received: true, duplicate: outcome === "duplicate" });
      return;
    }
    await reconcilePaystackRefundsForCapture(req.scope, attempt.reference, "webhook", fetch, signature);
    res.status(200).json({ received: true });
  } catch {
    // Paystack redelivers, and the scheduled reconciliation re-reads the same state.
    res.status(503).json({ message: "Paystack event is safely deferred for retry" });
  }
}
