import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { processPaymentWorkflow, updateCartWorkflow } from "@medusajs/medusa/core-flows";
import { ContainerRegistrationKeys, MedusaError, Modules, PaymentActions, PaymentSessionStatus } from "@medusajs/framework/utils";
import { releaseCheckoutHoldWithinLock, withCheckoutInventoryLock } from "../../../../../checkout-holds";
import { testPaymentEnabled } from "../../../../../test-payment-config";

const providerRegistrationId = "storefront-test_local";
const providerId = `pp_${providerRegistrationId}`;
type Outcome = "success" | "pending" | "declined" | "cancelled" | "unknown";
type RecordedEvent = { event_id: string; outcome: Outcome; status: string };
type PaymentSession = {
  id: string;
  amount: number;
  currency_code: string;
  status: string;
  provider_id: string;
  payment_collection_id: string;
  data?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
};

async function orderForCart(req: MedusaRequest, cartId: string): Promise<string | null> {
  const query = req.scope.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({ entity: "order_cart", fields: ["order_id"], filters: { cart_id: cartId } });
  return typeof data[0]?.order_id === "string" ? data[0].order_id : null;
}

async function markEvent(req: MedusaRequest, session: PaymentSession, record: RecordedEvent, data: Record<string, unknown>, status: PaymentSessionStatus): Promise<void> {
  const oldEvents = Array.isArray(session.metadata?.storefront_test_events)
    ? session.metadata.storefront_test_events as RecordedEvent[] : [];
  const events = [...oldEvents.filter((entry) => entry.event_id !== record.event_id), record];
  if (events.length > 100) throw new MedusaError(MedusaError.Types.CONFLICT, "This test payment session has reached its event limit");
  const payment = req.scope.resolve(Modules.PAYMENT);
  await payment.updatePaymentSession({
    id: session.id,
    amount: session.amount,
    currency_code: session.currency_code,
    data,
    status,
    metadata: { ...(session.metadata || {}), storefront_test_events: events },
  });
}

export async function POST(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  res.setHeader("Cache-Control", "private, no-store, max-age=0");
  try {
    if (!testPaymentEnabled()) throw new MedusaError(MedusaError.Types.NOT_ALLOWED, "Test payment simulation is disabled");
    const body = req.body as Record<string, unknown>;
    const sessionId = typeof body?.session_id === "string" ? body.session_id : "";
    const eventId = typeof body?.event_id === "string" ? body.event_id : "";
    const outcome = body?.outcome;
    if (!/^payses_[A-Za-z0-9_-]+$/.test(sessionId) || !/^[A-Za-z0-9_-]{8,128}$/.test(eventId) ||
      !["success", "pending", "declined", "cancelled", "unknown"].includes(String(outcome))) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "The test payment event is invalid");
    }

    const result = await withCheckoutInventoryLock(req.scope, async () => {
      const cartId = req.params.id;
      const query = req.scope.resolve(ContainerRegistrationKeys.QUERY);
      const { data: sessions } = await query.graph({
        entity: "payment_session",
        fields: ["id", "amount", "currency_code", "status", "provider_id", "payment_collection_id", "data", "metadata"],
        filters: { id: sessionId, provider_id: providerId },
      });
      const session = sessions[0] as PaymentSession | undefined;
      if (!session) throw new MedusaError(MedusaError.Types.NOT_FOUND, "Test payment session not found");
      const { data: cartLinks } = await query.graph({
        entity: "cart_payment_collection", fields: ["cart_id"], filters: { payment_collection_id: session.payment_collection_id },
      });
      if (cartLinks[0]?.cart_id !== cartId) throw new MedusaError(MedusaError.Types.NOT_FOUND, "Test payment session not found");

      const recorded = Array.isArray(session.metadata?.storefront_test_events)
        ? session.metadata.storefront_test_events as RecordedEvent[] : [];
      const prior = recorded.find((entry) => entry.event_id === eventId);
      if (prior && prior.outcome !== outcome) {
        throw new MedusaError(MedusaError.Types.CONFLICT, "A payment event ID cannot be reused for a different outcome");
      }
      if (prior) {
        const existingOrderId = await orderForCart(req, cartId);
        if (existingOrderId) return { status: "captured", order_id: existingOrderId, duplicate: true };
        if (prior.status !== "processing" || prior.outcome !== "success") {
          return { status: prior.status, order_id: null, duplicate: true };
        }
      }

      // Once an order is committed, a late provider event cannot turn its
      // payment session back into a declined, cancelled, or pending state.
      const committedOrderId = await orderForCart(req, cartId);
      if (committedOrderId) {
        return { status: "captured", order_id: committedOrderId, duplicate: true };
      }

      const eventOutcome = outcome as Outcome;
      const eventData = { ...(session.data || {}), outcome: eventOutcome };
      if (eventOutcome === "unknown") {
        await markEvent(req, session, { event_id: eventId, outcome: eventOutcome, status: "unknown" }, eventData, PaymentSessionStatus.PENDING);
        return { status: "unknown", order_id: null, duplicate: false };
      }
      if (eventOutcome === "pending" || eventOutcome === "declined" || eventOutcome === "cancelled") {
        const status = eventOutcome === "declined" ? PaymentSessionStatus.ERROR
          : eventOutcome === "cancelled" ? PaymentSessionStatus.CANCELED : PaymentSessionStatus.PENDING;
        await markEvent(req, session, { event_id: eventId, outcome: eventOutcome, status: eventOutcome }, eventData, status);
        return { status: eventOutcome, order_id: null, duplicate: false };
      }

      const existingOrderId = await orderForCart(req, cartId);
      if (existingOrderId) {
        await markEvent(req, session, { event_id: eventId, outcome: eventOutcome, status: "captured" }, eventData, PaymentSessionStatus.CAPTURED);
        return { status: "captured", order_id: existingOrderId, duplicate: true };
      }

      await markEvent(req, session, { event_id: eventId, outcome: eventOutcome, status: "processing" }, eventData, PaymentSessionStatus.PENDING);
      await releaseCheckoutHoldWithinLock(req.scope, cartId);
      const payment = req.scope.resolve(Modules.PAYMENT);
      const processed = await payment.getWebhookActionAndData({
          provider: providerRegistrationId,
        payload: {
          data: { event_id: eventId, session_id: session.id, amount: session.amount, outcome: eventOutcome },
          rawData: JSON.stringify({ event_id: eventId, session_id: session.id, outcome: eventOutcome }),
          headers: {},
        },
      });
      if (processed.action !== PaymentActions.SUCCESSFUL || !processed.data?.session_id) {
        throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "The test provider rejected its success event");
      }

      let completionError: unknown;
      try { await processPaymentWorkflow(req.scope).run({ input: processed }); }
      catch (error) { completionError = error; }
      const orderId = await orderForCart(req, cartId);
      if (orderId) {
        await markEvent(req, session, { event_id: eventId, outcome: eventOutcome, status: "captured" }, eventData, PaymentSessionStatus.CAPTURED);
        return { status: "captured", order_id: orderId, duplicate: false };
      }

      const { data: carts } = await query.graph({ entity: "cart", fields: ["id", "metadata"], filters: { id: cartId } });
      const cart = carts[0] as { id: string; metadata?: Record<string, unknown> | null } | undefined;
      if (cart) {
        await updateCartWorkflow(req.scope).run({ input: {
          id: cartId,
          metadata: {
            ...(cart.metadata || {}),
            storefront_payment_exception: {
              session_id: session.id,
              event_id: eventId,
              status: "paid_exception",
              recorded_at: new Date().toISOString(),
              reason: "Payment succeeded but the durable order reservation needs recovery",
            },
          },
        } });
      }
      await markEvent(req, session, { event_id: eventId, outcome: eventOutcome, status: "paid_exception" }, eventData, PaymentSessionStatus.CAPTURED);
      return { status: "paid_exception", order_id: null, duplicate: false, error: completionError instanceof Error ? completionError.message : undefined };
    });
    res.status(result.status === "paid_exception" ? 202 : 200).json({
      payment: { status: result.status, duplicate: result.duplicate },
    });
  } catch (error) {
    const status = error instanceof MedusaError && error.type === MedusaError.Types.INVALID_DATA ? 400
      : error instanceof MedusaError && error.type === MedusaError.Types.NOT_FOUND ? 404
      : error instanceof MedusaError && error.type === MedusaError.Types.NOT_ALLOWED ? 404
      : error instanceof MedusaError && error.type === MedusaError.Types.CONFLICT ? 409
      : 503;
    res.status(status).json({ message: error instanceof Error ? error.message : "Test payment event failed" });
  }
}
