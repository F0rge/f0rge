import type { MedusaContainer } from "@medusajs/framework/types";
import { processPaymentWorkflow, updateCartWorkflow } from "@medusajs/medusa/core-flows";
import { ContainerRegistrationKeys, Modules, PaymentActions, PaymentSessionStatus } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { checkoutHoldForCart, releaseCheckoutHoldWithinLock, withCheckoutInventoryLock } from "./checkout-holds";
import { medusaAmountToMinor, peachAccessToken, peachCheckoutStatus, parsePeachStatusResponse } from "./peach-checkout";
import { PEACH_PAYMENT_PROVIDER_ID, peachPaymentConfig } from "./peach-payment-config";
import {
  claimPeachAttemptStatusCheck, claimPeachWebhook, completePeachWebhook, findPeachAttemptByReference,
  findPeachAttemptBySession, listPeachAttemptsForStatusCheck, peachEventCanAdvance, receivePeachWebhook, retryPeachWebhook, updatePeachAttempt,
  type PeachInboxEvent,
} from "./peach-payment-store";
import { prepareStorefrontOrderHandoff } from "./storefront-order-handoff";
import { processClaimedPeachRefundWebhook } from "./storefront-peach-refunds";

const providerRegistrationId = "peach_sandbox";
type Container = MedusaContainer;
type PaymentSession = {
  id: string;
  amount: unknown;
  currency_code: string;
  status: string;
  provider_id: string;
  payment_collection_id: string;
  data?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
};

/** Reconciles known checkouts through Peach's read-only V2 status endpoint. */
export async function reconcilePeachCheckoutStatuses(container: Container, paymentSessionId?: string): Promise<number> {
  const config = peachPaymentConfig();
  if (!config) return 0;
  const db = container.resolve(ContainerRegistrationKeys.PG_CONNECTION) as Knex;
  const targeted = paymentSessionId ? await findPeachAttemptBySession(db, paymentSessionId) : undefined;
  const attempts = paymentSessionId ? (targeted ? [targeted] : []) : await listPeachAttemptsForStatusCheck(db);
  if (!attempts.length) return 0;

  let token: string;
  try { token = (await peachAccessToken(config)).token; }
  catch { return 0; }

  let observations = 0;
  for (const attempt of attempts) {
    if (!attempt.checkout_id || !await claimPeachAttemptStatusCheck(db, attempt.id)) continue;
    try {
      const body = await peachCheckoutStatus(config, attempt.checkout_id, token);
      const event = parsePeachStatusResponse(body);
      if (!event || event.checkout_id !== attempt.checkout_id ||
        event.merchant_reference !== attempt.merchant_reference ||
        event.amount_minor !== Number(attempt.amount_minor) || event.currency_code !== attempt.currency_code ||
        event.payment_type !== "DB") continue;

      const received = await receivePeachWebhook(db, event, null, "status");
      const claimed = await claimPeachWebhook(db, received.id);
      if (!claimed) continue;
      try { await processClaimedPeachWebhook(container, db, claimed); }
      catch {
        try { await retryPeachWebhook(db, claimed.id, claimed.lease_token, "status_reconciliation_failed"); }
        catch { /* The durable inbox row remains recoverable by the webhook worker. */ }
      }
      observations += 1;
    } catch {
      // Keep pending attempts available for the next scheduled status query.
    }
  }
  return observations;
}

export async function processNextPeachWebhook(container: Container): Promise<boolean> {
  const db = container.resolve(ContainerRegistrationKeys.PG_CONNECTION) as Knex;
  const event = await claimPeachWebhook(db);
  if (!event) return false;
  try { await processClaimedPeachWebhook(container, db, event); }
  catch {
    try { await retryPeachWebhook(db, event.id, event.lease_token, "worker_processing_failed"); }
    catch { /* A newer worker owns the lease or the database is temporarily unavailable. */ }
  }
  return true;
}

export async function processClaimedPeachWebhook(container: Container, db: Knex, event: PeachInboxEvent): Promise<"processed" | "ignored" | "paid_exception"> {
  if (event.payment_type === "RF") {
    const outcome = await processClaimedPeachRefundWebhook(container, db, event);
    if (outcome === "needs_review") {
      await completePeachWebhook(db, event.id, event.lease_token, "needs_review");
      return "ignored";
    }
    await completePeachWebhook(db, event.id, event.lease_token, "processed");
    return "processed";
  }
  if (event.payment_type !== "DB") {
    await completePeachWebhook(db, event.id, event.lease_token, "ignored");
    return "ignored";
  }

  const state = event.result_state;
  const eventId = event.webhook_id || event.event_key;
  return withCheckoutInventoryLock(container, async () => {
    // Re-read the attempt after acquiring the shared inventory lock. Peach can
    // deliver success after cancel/uncertain, and older callbacks can race it.
    const attempt = await findPeachAttemptByReference(db, event.merchant_reference);
    if (!attempt || Number(attempt.amount_minor) !== Number(event.amount_minor) || attempt.currency_code !== event.currency_code ||
      (attempt.checkout_id && attempt.checkout_id !== event.checkout_id)) {
      await completePeachWebhook(db, event.id, event.lease_token, "ignored");
      return "ignored";
    }
    if (!peachEventCanAdvance(attempt, event)) {
      await completePeachWebhook(db, event.id, event.lease_token, "ignored");
      return "ignored";
    }
    if (!attempt.checkout_id) await updatePeachAttempt(db, attempt.id, { checkout_id: event.checkout_id });

    const query = container.resolve(ContainerRegistrationKeys.QUERY);
    const { data: sessions } = await query.graph({
      entity: "payment_session",
      fields: ["id", "amount", "currency_code", "status", "provider_id", "payment_collection_id", "data", "metadata"],
      filters: { id: attempt.payment_session_id, provider_id: PEACH_PAYMENT_PROVIDER_ID },
    });
    const session = sessions[0] as unknown as PaymentSession | undefined;
    if (!session || medusaAmountToMinor(session.amount) !== Number(event.amount_minor) ||
      session.currency_code.toUpperCase() !== event.currency_code) {
      if (state !== "paid") {
        await completePeachWebhook(db, event.id, event.lease_token, "ignored");
        return "ignored";
      }
      // Native session invalidation cannot revoke an external charge. The
      // attempt and verified inbox, including the original checkout snapshot,
      // remain the operator's recovery source even if no cart survives.
      await updatePeachAttempt(db, attempt.id, {
        status: "captured", last_event_timestamp: event.event_timestamp, last_event_state: state,
        ...(event.transaction_id ? { captured_transaction_id: event.transaction_id } : {}),
      });
      let originalCartId = attempt.cart_id;
      if (!originalCartId) {
        // Backfill recovery context for pre-migration attempts when Medusa's
        // soft-deleted session still retains its original collection link.
        const nativeSession = await db("payment_session").where({ id: attempt.payment_session_id }).first();
        if (nativeSession?.payment_collection_id) {
          const { data: links } = await query.graph({ entity: "cart_payment_collection", fields: ["cart_id"],
            filters: { payment_collection_id: nativeSession.payment_collection_id } });
          originalCartId = typeof links[0]?.cart_id === "string" ? links[0].cart_id : null;
        }
      }
      if (originalCartId) await savePaidException(container, query, originalCartId, attempt.captured_order_id, attempt.payment_session_id, eventId);
      await completePeachWebhook(db, event.id, event.lease_token, "paid_exception");
      return "paid_exception";
    }

    const { data: cartLinks } = await query.graph({
      entity: "cart_payment_collection", fields: ["cart_id"], filters: { payment_collection_id: session.payment_collection_id },
    });
    const cartId = typeof cartLinks[0]?.cart_id === "string" ? cartLinks[0].cart_id : "";
    if (!cartId) {
      await completePeachWebhook(db, event.id, event.lease_token, "ignored");
      return "ignored";
    }
    const payment = container.resolve(Modules.PAYMENT);
    const sessionData = {
      ...(session.data || {}), peach_status: state, peach_checkout_id: event.checkout_id,
      ...(event.transaction_id ? { peach_transaction_id: event.transaction_id } : {}),
    };
    const sessionMetadata = {
      ...(session.metadata || {}),
      storefront_peach: {
        source: event.source,
        event_id: eventId,
        result_code: event.result_code,
        status: state,
        transaction_id: event.transaction_id,
        updated_at: new Date().toISOString(),
      },
    };
    const setSessionStatus = async (status: PaymentSessionStatus): Promise<void> => {
      await payment.updatePaymentSession({
        id: session.id, amount: session.amount as string, currency_code: session.currency_code,
        data: sessionData, metadata: sessionMetadata, status,
      });
    };

    const { data: linkedOrders } = await query.graph({
      entity: "order_cart", fields: ["order_id"], filters: { cart_id: cartId },
    });
    const orderId = typeof linkedOrders[0]?.order_id === "string" ? linkedOrders[0].order_id : null;
    if (orderId) {
      if (state === "paid") {
        await setSessionStatus(PaymentSessionStatus.CAPTURED);
        try { await prepareStorefrontOrderHandoff(container, orderId); }
        catch { await savePaidException(container, query, cartId, orderId, session.id, eventId); }
        await updatePeachAttempt(db, attempt.id, {
          status: "captured", last_event_timestamp: event.event_timestamp, last_event_state: state,
          ...(event.transaction_id ? { captured_transaction_id: event.transaction_id } : {}), captured_order_id: orderId,
        });
      }
      await completePeachWebhook(db, event.id, event.lease_token, "processed");
      return "processed";
    }

    if (state !== "paid") {
      const status = state === "declined" ? PaymentSessionStatus.ERROR
        : state === "cancelled" ? PaymentSessionStatus.CANCELED : PaymentSessionStatus.PENDING;
      await setSessionStatus(status);
      await updatePeachAttempt(db, attempt.id, {
        status: state, last_event_timestamp: event.event_timestamp, last_event_state: state,
      });
      await completePeachWebhook(db, event.id, event.lease_token, state === "unknown" ? "ignored" : "processed");
      return "processed";
    }

    const hold = await checkoutHoldForCart(container, cartId);
    if (!hold.ready) {
      await savePaidException(container, query, cartId, null, session.id, eventId);
      await setSessionStatus(PaymentSessionStatus.CAPTURED);
      await updatePeachAttempt(db, attempt.id, {
        status: "captured", last_event_timestamp: event.event_timestamp, last_event_state: state,
        ...(event.transaction_id ? { captured_transaction_id: event.transaction_id } : {}),
      });
      await completePeachWebhook(db, event.id, event.lease_token, "paid_exception");
      return "paid_exception";
    }

    // The signed Peach success means the charge is already captured. Persist
    // that fact before Medusa invokes authorizePayment from the success
    // workflow, which now requires this durable confirmation.
    await updatePeachAttempt(db, attempt.id, {
      status: "captured", last_event_timestamp: event.event_timestamp, last_event_state: state,
      ...(event.transaction_id ? { captured_transaction_id: event.transaction_id } : {}),
    });
    await setSessionStatus(PaymentSessionStatus.PENDING);
    await releaseCheckoutHoldWithinLock(container, cartId);
    const processed = await payment.getWebhookActionAndData({
      provider: providerRegistrationId,
      payload: { data: { ...event, amount_minor: Number(event.amount_minor) }, rawData: JSON.stringify({ ...event }), headers: {} },
    });
    if (processed.action !== PaymentActions.SUCCESSFUL || processed.data?.session_id !== session.id) {
      throw new Error("Peach provider rejected a verified success event");
    }

    try { await processPaymentWorkflow(container).run({ input: processed }); }
    catch { /* The committed order lookup below distinguishes a recoverable late failure. */ }
    const { data: ordersAfterPayment } = await query.graph({
      entity: "order_cart", fields: ["order_id"], filters: { cart_id: cartId },
    });
    const committedOrderId = typeof ordersAfterPayment[0]?.order_id === "string" ? ordersAfterPayment[0].order_id : null;
    if (committedOrderId) {
      await setSessionStatus(PaymentSessionStatus.CAPTURED);
      try { await prepareStorefrontOrderHandoff(container, committedOrderId); }
      catch { await savePaidException(container, query, cartId, committedOrderId, session.id, eventId); }
      await updatePeachAttempt(db, attempt.id, {
        status: "captured", last_event_timestamp: event.event_timestamp, last_event_state: state,
        ...(event.transaction_id ? { captured_transaction_id: event.transaction_id } : {}), captured_order_id: committedOrderId,
      });
      await completePeachWebhook(db, event.id, event.lease_token, "processed");
      return "processed";
    }

    await savePaidException(container, query, cartId, null, session.id, eventId);
    await setSessionStatus(PaymentSessionStatus.CAPTURED);
    await updatePeachAttempt(db, attempt.id, {
      status: "captured", last_event_timestamp: event.event_timestamp, last_event_state: state,
      ...(event.transaction_id ? { captured_transaction_id: event.transaction_id } : {}),
    });
    await completePeachWebhook(db, event.id, event.lease_token, "paid_exception");
    return "paid_exception";
  });
}

async function savePaidException(
  container: Container,
  query: { graph(input: Record<string, unknown>): Promise<{ data: Record<string, unknown>[] }> },
  cartId: string,
  orderId: string | null,
  sessionId: string,
  eventId: string,
): Promise<void> {
  const { data: carts } = await query.graph({ entity: "cart", fields: ["id", "metadata"], filters: { id: cartId } });
  const cart = carts[0] as { id: string; metadata?: Record<string, unknown> | null } | undefined;
  if (cart) {
    await updateCartWorkflow(container).run({ input: {
      id: cartId,
      metadata: {
        ...(cart.metadata || {}),
        storefront_payment_exception: {
          session_id: sessionId, event_id: eventId, order_id: orderId, status: "paid_exception",
          recorded_at: new Date().toISOString(), reason: "Payment succeeded; inventory or order handoff needs operator recovery",
        },
      },
    } });
  }
  if (!orderId) return;
  const { data: orders } = await query.graph({ entity: "order", fields: ["id", "metadata"], filters: { id: orderId } });
  const order = orders[0] as { id: string; metadata?: Record<string, unknown> | null } | undefined;
  if (!order) return;
  const orderModule = container.resolve(Modules.ORDER);
  await orderModule.updateOrders([{
    id: orderId,
    metadata: {
      ...(order.metadata || {}),
      storefront_capacity_exception: {
        status: "paid_exception", event_id: eventId, recorded_at: new Date().toISOString(),
        reason: "Payment succeeded; order handoff needs operator recovery",
      },
    },
  }]);
}
