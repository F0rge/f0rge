import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { parsePeachWebhook, verifyPeachWebhookSignature } from "../../../peach-checkout";
import { peachPaymentConfig } from "../../../peach-payment-config";
import {
  claimPeachWebhook, findPeachAttemptByReference, receivePeachWebhook, retryPeachWebhook,
  type PeachInboxEvent,
} from "../../../peach-payment-store";
import { processClaimedPeachWebhook } from "../../../peach-webhook-processing";

function header(req: MedusaRequest, name: string): string | undefined {
  const value = req.headers[name];
  return typeof value === "string" ? value : undefined;
}

function rawBody(value: unknown): Buffer | undefined {
  if (Buffer.isBuffer(value)) return value;
  if (typeof value === "string") return Buffer.from(value, "utf8");
  if (value instanceof Uint8Array) return Buffer.from(value);
  return undefined;
}

export async function POST(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  res.setHeader("Cache-Control", "no-store");
  const config = peachPaymentConfig();
  if (!config) {
    res.status(404).json({ message: "Peach callback is unavailable" });
    return;
  }

  const body = rawBody(req.rawBody);
  const webhookId = header(req, "x-webhook-id");
  const signature = header(req, "x-webhook-signature");
  const valid = verifyPeachWebhookSignature({
    secret: config.webhookSecret,
    configuredUrl: config.webhookUrl,
    timestamp: header(req, "x-webhook-timestamp"),
    webhookId,
    signature,
    algorithm: header(req, "x-webhook-signature-algorithm"),
    rawBody: body,
  });
  if (!valid || !body || !webhookId || !signature) {
    res.status(401).json({ message: "Peach callback signature is invalid" });
    return;
  }

  const contentType = header(req, "content-type")?.split(";", 1)[0]?.trim().toLowerCase();
  if (contentType === "application/json") {
    // Peach's initial signed webhook configuration handshake is JSON. It is
    // acknowledged separately and never enters the payment event processor.
    res.status(200).json({ received: true });
    return;
  }
  if (contentType !== "application/x-www-form-urlencoded") {
    res.status(415).json({ message: "Unsupported Peach callback content type" });
    return;
  }

  const event = parsePeachWebhook(body, webhookId);
  if (!event) {
    res.status(400).json({ message: "Peach payment event is invalid" });
    return;
  }

  const db = req.scope.resolve(ContainerRegistrationKeys.PG_CONNECTION) as Knex;
  const attempt = await findPeachAttemptByReference(db, event.merchant_reference);
  if (!attempt) {
    res.status(404).json({ message: "Peach payment attempt was not found" });
    return;
  }

  let claimedEvent: PeachInboxEvent | undefined;
  try {
    const inbox = await receivePeachWebhook(db, event, signature);
    const claimed = await claimPeachWebhook(db, inbox.id);
    if (!claimed) {
      res.status(200).json({ received: true, duplicate: true });
      return;
    }
    claimedEvent = claimed;
    const result = await processClaimedPeachWebhook(req.scope, db, claimed);
    if (result === "ignored" && event.payment_type !== "RF") {
      res.status(409).json({ message: "Peach payment event did not match its stored attempt" });
      return;
    }
    res.status(200).json({ received: true, duplicate: inbox.duplicate });
  } catch {
    if (claimedEvent) {
      try { await retryPeachWebhook(db, claimedEvent.id, claimedEvent.lease_token, "processing_failed"); }
      catch { /* The committed inbox row remains recoverable by the scheduled worker. */ }
    }
    res.status(503).json({ message: "Peach payment event is safely queued for retry" });
  }
}
