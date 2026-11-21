import type {
  AuthorizePaymentInput, AuthorizePaymentOutput, CancelPaymentInput, CancelPaymentOutput,
  CapturePaymentInput, CapturePaymentOutput, DeletePaymentInput, DeletePaymentOutput,
  GetPaymentStatusInput, GetPaymentStatusOutput, InitiatePaymentInput, InitiatePaymentOutput,
  ProviderWebhookPayload, RefundPaymentInput, RefundPaymentOutput, RetrievePaymentInput,
  RetrievePaymentOutput, UpdatePaymentInput, UpdatePaymentOutput, WebhookActionResult,
} from "@medusajs/framework/types";
import { AbstractPaymentProvider, ContainerRegistrationKeys, PaymentActions, PaymentSessionStatus } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { initializePaystackTransaction, medusaAmountToMinor, minorToMajor } from "../../paystack-checkout";
import { paystackPaymentConfig } from "../../paystack-payment-config";
import {
  claimPaystackRefundForMedusa, createPaystackAttempt, findPaystackAttemptByReference, findPaystackAttemptBySession,
  updatePaystackAttempt, type PaystackAttempt,
} from "../../paystack-payment-store";

const NO_DATA = {};
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function paystackPaymentSessionStatus(state: unknown): PaymentSessionStatus {
  if (state === "declined") return PaymentSessionStatus.ERROR;
  if (state === "paid" || state === "captured") return PaymentSessionStatus.CAPTURED;
  return PaymentSessionStatus.PENDING;
}

export class StorefrontPaystackPaymentProvider extends AbstractPaymentProvider {
  static identifier = "paystack";

  constructor(container: Record<string, unknown>, config: Record<string, unknown> = {}) {
    super(container, config);
  }

  async initiatePayment(input: InitiatePaymentInput): Promise<InitiatePaymentOutput> {
    const config = paystackPaymentConfig();
    if (!config) throw new Error("Paystack checkout is not configured");
    const sessionId = input.context?.idempotency_key;
    const amountMinor = medusaAmountToMinor(input.amount);
    const currency = input.currency_code.toUpperCase();
    const email = typeof input.data?.storefront_customer_email === "string" ? input.data.storefront_customer_email : "";
    if (!sessionId || currency !== "ZAR" || amountMinor === null || amountMinor <= 0) {
      throw new Error("Paystack checkout requires a valid Medusa payment session, ZAR currency, and amount");
    }
    if (!EMAIL.test(email) || email.length > 254) throw new Error("Paystack checkout requires the customer's email address");

    const db = this.db();
    const existing = await findPaystackAttemptBySession(db, sessionId);
    if (existing) return this.existingAttempt(existing);

    // Persist the unique reference before the initialize POST. Paystack
    // rejects a reused reference, so an ambiguous POST can never create two
    // transactions, and the verify endpoint can always reconcile it.
    const { attempt, created } = await createPaystackAttempt(db, {
      paymentSessionId: sessionId, amountMinor, currencyCode: currency,
      cartId: typeof input.data?.storefront_cart_id === "string" ? input.data.storefront_cart_id : null,
      checkoutSnapshot: input.data?.storefront_checkout_snapshot && typeof input.data.storefront_checkout_snapshot === "object"
        ? input.data.storefront_checkout_snapshot as Record<string, unknown> : null,
    });
    if (!created) return this.existingAttempt(attempt);

    let response: Response;
    try {
      response = await initializePaystackTransaction(config, {
        email, amountMinor: Number(attempt.amount_minor), currencyCode: attempt.currency_code, reference: attempt.reference,
        metadata: { payment_session_id: sessionId, ...(attempt.cart_id ? { cart_id: attempt.cart_id } : {}) },
      });
    } catch {
      await updatePaystackAttempt(db, attempt.id, { status: "initiation_unknown" });
      return this.pendingOutput(attempt, "initiation_unknown");
    }

    if (!response.ok) {
      if (response.status >= 500 || response.status === 429) {
        await updatePaystackAttempt(db, attempt.id, { status: "initiation_unknown" });
        return this.pendingOutput(attempt, "initiation_unknown");
      }
      await updatePaystackAttempt(db, attempt.id, { status: "declined" });
      return { id: attempt.reference, status: PaymentSessionStatus.ERROR, data: this.sessionData(attempt, "declined") };
    }

    let body: Record<string, unknown>;
    try { body = await response.json() as Record<string, unknown>; }
    catch {
      await updatePaystackAttempt(db, attempt.id, { status: "initiation_unknown" });
      return this.pendingOutput(attempt, "initiation_unknown");
    }
    const data = body.data && typeof body.data === "object" ? body.data as Record<string, unknown> : {};
    const redirectUrl = typeof data.authorization_url === "string" ? data.authorization_url : "";
    if (body.status !== true || data.reference !== attempt.reference || !this.isPaystackCheckout(redirectUrl)) {
      await updatePaystackAttempt(db, attempt.id, { status: "initiation_unknown" });
      return this.pendingOutput(attempt, "initiation_unknown");
    }
    await updatePaystackAttempt(db, attempt.id, { authorization_url: redirectUrl, status: "checkout_created" });
    return {
      id: attempt.reference,
      status: PaymentSessionStatus.PENDING,
      data: this.sessionData(attempt, "checkout_created", { redirect_url: redirectUrl }),
    };
  }

  async authorizePayment(input: AuthorizePaymentInput): Promise<AuthorizePaymentOutput> {
    const attempt = await this.requireVerifiedCapturedAttempt(input.data, input.context?.idempotency_key);
    return {
      // A verified Paystack success is already a captured charge. CAPTURED
      // makes Medusa record its native capture without a second request.
      status: PaymentSessionStatus.CAPTURED,
      data: {
        ...(input.data || {}),
        paystack_status: "captured",
        paystack_authorized_payment_session_id: attempt.payment_session_id,
        // Firstout stores this as the capture identity that refunds target.
        transaction_id: attempt.reference,
        ...(attempt.transaction_id ? { provider_payment_id: attempt.transaction_id } : {}),
      },
    };
  }

  async capturePayment(_input: CapturePaymentInput): Promise<CapturePaymentOutput> {
    throw new Error("Separate Paystack capture is unsupported; use verified hosted checkout");
  }

  async getPaymentStatus(input: GetPaymentStatusInput): Promise<GetPaymentStatusOutput> {
    return { status: paystackPaymentSessionStatus(input.data?.paystack_status) };
  }

  async retrievePayment(input: RetrievePaymentInput): Promise<RetrievePaymentOutput> { return { data: input.data || {} }; }
  async updatePayment(input: UpdatePaymentInput): Promise<UpdatePaymentOutput> { return { data: input.data || {}, status: PaymentSessionStatus.PENDING }; }
  async deletePayment(_input: DeletePaymentInput): Promise<DeletePaymentOutput> { return { data: NO_DATA }; }

  async refundPayment(input: RefundPaymentInput): Promise<RefundPaymentOutput> {
    // Medusa's native Admin refund path is denied unless our reconciliation
    // workflow created this exact Refund row with a one-use capability.
    // A verified Paystack refund is already complete; this callback only
    // records Medusa's native financial artifact and never calls Paystack.
    const context = input.context as { idempotency_key?: unknown } | undefined;
    const refundId = typeof context?.idempotency_key === "string" ? context.idempotency_key : "";
    const row = refundId ? await this.db()("refund").where({ id: refundId }).whereNull("deleted_at").first() as
      { id: string; payment_id: string; amount: unknown; metadata?: unknown } | undefined : undefined;
    const metadata = row?.metadata && typeof row.metadata === "object" && !Array.isArray(row.metadata)
      ? (row.metadata as Record<string, unknown>).storefront_paystack_refund : undefined;
    const proof = metadata && typeof metadata === "object" && !Array.isArray(metadata)
      ? metadata as Record<string, unknown> : {};
    const amountMinor = medusaAmountToMinor(input.amount);
    const dispatchId = typeof proof.request_id === "string" ? proof.request_id : "";
    const providerRefundId = typeof proof.provider_refund_id === "string" ? proof.provider_refund_id : "";
    const capability = typeof proof.authorization_key === "string" ? proof.authorization_key : "";
    if (!row || !row.payment_id || amountMinor === null || !dispatchId || !providerRefundId || !capability ||
      amountMinor !== medusaAmountToMinor(row.amount)) {
      throw new Error("Paystack refunds require a matching verified Storefront reconciliation intent");
    }
    const claimed = await claimPaystackRefundForMedusa(this.db(), {
      requestId: dispatchId, providerRefundId, capability, paymentId: row.payment_id,
      refundId: row.id, amountMinor,
    });
    if (!claimed) throw new Error("Paystack refund intent is not verified for this payment or was already consumed");
    return { data: input.data || {} };
  }

  async cancelPayment(input: CancelPaymentInput): Promise<CancelPaymentOutput> {
    return { data: { ...(input.data || {}), provider: "paystack" } };
  }

  async getWebhookActionAndData(input: ProviderWebhookPayload["payload"]): Promise<WebhookActionResult> {
    const event = input.data as Record<string, unknown>;
    const reference = typeof event.reference === "string" ? event.reference : "";
    const attempt = reference ? await findPaystackAttemptByReference(this.db(), reference) : undefined;
    if (!attempt) return { action: PaymentActions.NOT_SUPPORTED };

    const amountMinor = typeof event.amount_minor === "number" ? event.amount_minor : null;
    const currency = typeof event.currency_code === "string" ? event.currency_code : "";
    if (event.kind !== "charge" || !Number.isSafeInteger(amountMinor) || amountMinor !== Number(attempt.amount_minor) ||
      currency !== attempt.currency_code) {
      return { action: PaymentActions.NOT_SUPPORTED };
    }
    // Only our isolated processor, after Paystack's verify endpoint confirmed
    // the charge, may advance an attempt to captured. The generic webhook
    // ingress is disabled; this only reports an already-durable paid fact.
    if (attempt.status !== "captured" || attempt.last_event_state !== "paid" || event.result_state !== "paid") {
      return { action: PaymentActions.NOT_SUPPORTED };
    }
    return {
      action: PaymentActions.SUCCESSFUL,
      data: { session_id: attempt.payment_session_id, amount: minorToMajor(Number(attempt.amount_minor)) },
    };
  }

  private db(): Knex {
    return this.container[ContainerRegistrationKeys.PG_CONNECTION] as Knex;
  }

  private async requireVerifiedCapturedAttempt(data: Record<string, unknown> | undefined, sessionId: string | undefined): Promise<PaystackAttempt> {
    const reference = typeof data?.paystack_reference === "string" ? data.paystack_reference : "";
    const attempt = reference ? await findPaystackAttemptByReference(this.db(), reference) : undefined;
    const amountMinor = typeof data?.paystack_amount_minor === "number" ? data.paystack_amount_minor : null;
    const isPaidSessionData = data?.paystack_status === "paid" || data?.paystack_status === "captured";
    if (!attempt || !sessionId || attempt.payment_session_id !== sessionId || attempt.status !== "captured" ||
      attempt.last_event_state !== "paid" || !isPaidSessionData || amountMinor !== Number(attempt.amount_minor) ||
      data?.currency_code !== attempt.currency_code) {
      throw new Error("Paystack payment is not verified as captured for this payment session");
    }
    return attempt;
  }

  private existingAttempt(attempt: PaystackAttempt | undefined): InitiatePaymentOutput {
    if (!attempt) throw new Error("Paystack payment attempt could not be recovered");
    const state = attempt.status === "checkout_created" ? "checkout_created" : "initiation_unknown";
    return {
      id: attempt.reference,
      status: PaymentSessionStatus.PENDING,
      data: this.sessionData(attempt, state, attempt.authorization_url ? { redirect_url: attempt.authorization_url } : {}),
    };
  }

  private pendingOutput(attempt: Pick<PaystackAttempt, "reference" | "amount_minor" | "currency_code">, state: string): InitiatePaymentOutput {
    return { id: attempt.reference, status: PaymentSessionStatus.PENDING, data: this.sessionData(attempt, state) };
  }

  private sessionData(attempt: Pick<PaystackAttempt, "reference" | "amount_minor" | "currency_code">, state: string, extra: Record<string, unknown> = {}): Record<string, unknown> {
    return {
      paystack_status: state,
      paystack_reference: attempt.reference,
      paystack_amount_minor: Number(attempt.amount_minor),
      currency_code: attempt.currency_code,
      ...extra,
    };
  }

  private isPaystackCheckout(value: string): boolean {
    try { return new URL(value).origin === "https://checkout.paystack.com"; }
    catch { return false; }
  }
}
