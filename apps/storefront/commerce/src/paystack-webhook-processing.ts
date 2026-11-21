import type { MedusaContainer } from "@medusajs/framework/types";
import { processPaymentWorkflow, updateCartWorkflow } from "@medusajs/medusa/core-flows";
import { ContainerRegistrationKeys, Modules, PaymentActions, PaymentSessionStatus } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { checkoutHoldForCart, releaseCheckoutHoldWithinLock, withCheckoutInventoryLock } from "./checkout-holds";
import { medusaAmountToMinor, verifyPaystackTransaction } from "./paystack-checkout";
import { PAYSTACK_PAYMENT_PROVIDER_ID, paystackPaymentConfig } from "./paystack-payment-config";
import {
  claimPaystackAttemptStatusCheck, claimPaystackObservation, completePaystackObservation, findPaystackAttemptByReference,
  findPaystackAttemptBySession, listPaystackAttemptsForStatusCheck, paystackEventCanAdvance, receivePaystackObservation,
  retryPaystackObservation, updatePaystackAttempt, type PaystackAttempt, type PaystackInboxEvent, type PaystackInboxSource,
} from "./paystack-payment-store";
import { prepareStorefrontOrderHandoff } from "./storefront-order-handoff";
import { processClaimedPaystackRefund } from "./storefront-paystack-refunds";

const providerRegistrationId = "paystack_checkout";
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

/**
 * Reads the authoritative charge state from Paystack's verify endpoint and
 * runs it through the durable inbox. A browser return or webhook body is
 * never payment proof on its own. Returns "not_found" when Paystack has no
 * transaction for the reference and "duplicate" when the fact was already handled.
 */
export async function verifyAndProcessPaystackCharge(
  container: Container,
  attempt: PaystackAttempt,
  source: PaystackInboxSource,
  signature: string | null = null,
  fetcher: typeof fetch = fetch,
): Promise<"processed" | "ignored" | "paid_exception" | "duplicate" | "not_found"> {
  const config = paystackPaymentConfig();
  if (!config) return "ignored";
  const db = container.resolve(ContainerRegistrationKeys.PG_CONNECTION) as Knex;
  const event = await verifyPaystackTransaction(config, attempt.reference, fetcher);
  if (!event) return "not_found";
  const received = await receivePaystackObservation(db, event, source, signature);
  const claimed = await claimPaystackObservation(db, received.id);
  if (!claimed) return "duplicate";
  try {
    return await processClaimedPaystackObservation(container, db, claimed);
  } catch (error) {
    try { await retryPaystackObservation(db, claimed.id, claimed.lease_token, "processing_failed"); }
    catch { /* The durable inbox row remains recoverable by the scheduled worker. */ }
    throw error;
  }
}

/**
 * Reconciles open attempts through Paystack's read-only verify endpoint, with
 * the window and backoff in listPaystackAttemptsForStatusCheck. A targeted
 * staff repair (payment session ID) ignores the window.
 */
export async function reconcilePaystackCheckoutStatuses(container: Container, paymentSessionId?: string, fetcher: typeof fetch = fetch): Promise<number> {
  if (!paystackPaymentConfig()) return 0;
  const db = container.resolve(ContainerRegistrationKeys.PG_CONNECTION) as Knex;
  const targeted = paymentSessionId ? await findPaystackAttemptBySession(db, paymentSessionId) : undefined;
  const attempts = paymentSessionId ? (targeted ? [targeted] : []) : await listPaystackAttemptsForStatusCheck(db);
  let observations = 0;
  for (const attempt of attempts) {
    if (!await claimPaystackAttemptStatusCheck(db, attempt.id, Boolean(paymentSessionId))) continue;
    try {
      const outcome = await verifyAndProcessPaystackCharge(container, attempt, "status", null, fetcher);
      if (outcome !== "not_found" && outcome !== "duplicate") observations += 1;
    } catch {
      // Keep the attempt available for the next scheduled status query.
    }
  }
  return observations;
}

export async function processNextPaystackObservation(container: Container): Promise<boolean> {
  const db = container.resolve(ContainerRegistrationKeys.PG_CONNECTION) as Knex;
  const event = await claimPaystackObservation(db);
  if (!event) return false;
  try { await processClaimedPaystackObservation(container, db, event); }
  catch {
    try { await retryPaystackObservation(db, event.id, event.lease_token, "worker_processing_failed"); }
    catch { /* A newer worker owns the lease or the database is temporarily unavailable. */ }
  }
  return true;
}

export async function processClaimedPaystackObservation(container: Container, db: Knex, event: PaystackInboxEvent): Promise<"processed" | "ignored" | "paid_exception"> {
  if (event.kind === "refund") {
    const outcome = await processClaimedPaystackRefund(container, db, event);
    await completePaystackObservation(db, event.id, event.lease_token, outcome === "needs_review" ? "needs_review" : "processed");
    return outcome === "needs_review" ? "ignored" : "processed";
  }
  if (event.kind !== "charge") {
    await completePaystackObservation(db, event.id, event.lease_token, "ignored");
    return "ignored";
  }

  const state = event.result_state;
  const eventId = event.event_key;
  return withCheckoutInventoryLock(container, async () => {
    // Re-read the attempt after acquiring the shared inventory lock. A success
    // can race older pending reads and a concurrent webhook.
    const attempt = await findPaystackAttemptByReference(db, event.reference);
    if (!attempt || Number(attempt.amount_minor) !== Number(event.amount_minor) || attempt.currency_code !== event.currency_code) {
      // "If the amount doesn't match, don't deliver value." The inbox row is retained for review.
      await completePaystackObservation(db, event.id, event.lease_token, attempt && state === "paid" ? "needs_review" : "ignored");
      return "ignored";
    }
    if (!paystackEventCanAdvance(attempt, event)) {
      await completePaystackObservation(db, event.id, event.lease_token, "ignored");
      return "ignored";
    }
    const capturedFields = {
      status: "captured", last_event_timestamp: event.event_timestamp, last_event_state: state,
      ...(event.transaction_id ? { transaction_id: event.transaction_id } : {}),
    };

    const query = container.resolve(ContainerRegistrationKeys.QUERY);
    const { data: sessions } = await query.graph({
      entity: "payment_session",
      fields: ["id", "amount", "currency_code", "status", "provider_id", "payment_collection_id", "data", "metadata"],
      filters: { id: attempt.payment_session_id, provider_id: PAYSTACK_PAYMENT_PROVIDER_ID },
    });
    const session = sessions[0] as unknown as PaymentSession | undefined;
    if (!session || medusaAmountToMinor(session.amount) !== Number(event.amount_minor) ||
      session.currency_code.toUpperCase() !== event.currency_code) {
      if (state !== "paid") {
        await completePaystackObservation(db, event.id, event.lease_token, "ignored");
        return "ignored";
      }
      // Native session invalidation cannot revoke an external charge. The
      // attempt and verified inbox, including the original checkout snapshot,
      // remain the operator's recovery source even if no cart survives.
      await updatePaystackAttempt(db, attempt.id, capturedFields);
      let originalCartId = attempt.cart_id;
      if (!originalCartId) {
        const nativeSession = await db("payment_session").where({ id: attempt.payment_session_id }).first();
        if (nativeSession?.payment_collection_id) {
          const { data: links } = await query.graph({ entity: "cart_payment_collection", fields: ["cart_id"],
            filters: { payment_collection_id: nativeSession.payment_collection_id } });
          originalCartId = typeof links[0]?.cart_id === "string" ? links[0].cart_id : null;
        }
      }
      if (originalCartId) await savePaidException(container, query, originalCartId, attempt.captured_order_id, attempt.payment_session_id, eventId);
      await completePaystackObservation(db, event.id, event.lease_token, "paid_exception");
      return "paid_exception";
    }

    const { data: cartLinks } = await query.graph({
      entity: "cart_payment_collection", fields: ["cart_id"], filters: { payment_collection_id: session.payment_collection_id },
    });
    const cartId = typeof cartLinks[0]?.cart_id === "string" ? cartLinks[0].cart_id : "";
    if (!cartId) {
      await completePaystackObservation(db, event.id, event.lease_token, "ignored");
      return "ignored";
    }
    const payment = container.resolve(Modules.PAYMENT);
    const sessionData = {
      ...(session.data || {}), paystack_status: state,
      ...(event.transaction_id ? { paystack_transaction_id: event.transaction_id } : {}),
    };
    const sessionMetadata = {
      ...(session.metadata || {}),
      storefront_paystack: {
        source: event.source,
        event_id: eventId,
        provider_status: event.provider_status,
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
        await updatePaystackAttempt(db, attempt.id, { ...capturedFields, captured_order_id: orderId });
      }
      await completePaystackObservation(db, event.id, event.lease_token, "processed");
      return "processed";
    }

    if (state !== "paid") {
      const status = state === "declined" ? PaymentSessionStatus.ERROR : PaymentSessionStatus.PENDING;
      await setSessionStatus(status);
      // Keep Paystack's own "abandoned" (the customer left the hosted page) apart
      // from in-progress pending: like declined, it is a confirmed non-payment
      // that is still re-checked but never raised as an uncertain payment.
      await updatePaystackAttempt(db, attempt.id, {
        status: event.provider_status === "abandoned" ? "abandoned" : state,
        last_event_timestamp: event.event_timestamp, last_event_state: state,
        ...(event.transaction_id ? { transaction_id: event.transaction_id } : {}),
      });
      await completePaystackObservation(db, event.id, event.lease_token, state === "unknown" ? "ignored" : "processed");
      return "processed";
    }

    const hold = await checkoutHoldForCart(container, cartId);
    if (!hold.ready) {
      await savePaidException(container, query, cartId, null, session.id, eventId);
      await setSessionStatus(PaymentSessionStatus.CAPTURED);
      await updatePaystackAttempt(db, attempt.id, capturedFields);
      await completePaystackObservation(db, event.id, event.lease_token, "paid_exception");
      return "paid_exception";
    }

    // A verified Paystack success is already captured. Persist that fact
    // before Medusa invokes authorizePayment from the success workflow, which
    // requires this durable confirmation.
    await updatePaystackAttempt(db, attempt.id, capturedFields);
    await setSessionStatus(PaymentSessionStatus.PENDING);
    await releaseCheckoutHoldWithinLock(container, cartId);
    const processed = await payment.getWebhookActionAndData({
      provider: providerRegistrationId,
      payload: { data: { ...event, amount_minor: Number(event.amount_minor) }, rawData: JSON.stringify({ ...event }), headers: {} },
    });
    if (processed.action !== PaymentActions.SUCCESSFUL || processed.data?.session_id !== session.id) {
      throw new Error("Paystack provider rejected a verified success observation");
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
      await updatePaystackAttempt(db, attempt.id, { ...capturedFields, captured_order_id: committedOrderId });
      await completePaystackObservation(db, event.id, event.lease_token, "processed");
      return "processed";
    }

    await savePaidException(container, query, cartId, null, session.id, eventId);
    await setSessionStatus(PaymentSessionStatus.CAPTURED);
    await updatePaystackAttempt(db, attempt.id, capturedFields);
    await completePaystackObservation(db, event.id, event.lease_token, "paid_exception");
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
