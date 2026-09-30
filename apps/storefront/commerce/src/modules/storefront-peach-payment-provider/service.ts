import type {
  AuthorizePaymentInput, AuthorizePaymentOutput, CancelPaymentInput, CancelPaymentOutput,
  CapturePaymentInput, CapturePaymentOutput, DeletePaymentInput, DeletePaymentOutput,
  GetPaymentStatusInput, GetPaymentStatusOutput, InitiatePaymentInput, InitiatePaymentOutput,
  ProviderWebhookPayload, RefundPaymentInput, RefundPaymentOutput, RetrievePaymentInput,
  RetrievePaymentOutput, UpdatePaymentInput, UpdatePaymentOutput, WebhookActionResult,
} from "@medusajs/framework/types";
import { AbstractPaymentProvider, ContainerRegistrationKeys, PaymentActions, PaymentSessionStatus } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { peachAccessToken, medusaAmountToMinor, minorToMajor, peachResultState } from "../../peach-checkout";
import { peachPaymentConfig } from "../../peach-payment-config";
import {
  createPeachAttempt, findPeachAttemptByReference, findPeachAttemptBySession, updatePeachAttempt,
  type PeachAttempt,
} from "../../peach-payment-store";

const NO_DATA = {};

export function peachPaymentSessionStatus(state: unknown): PaymentSessionStatus {
  if (state === "declined") return PaymentSessionStatus.ERROR;
  if (state === "cancelled") return PaymentSessionStatus.CANCELED;
  if (state === "paid" || state === "captured") return PaymentSessionStatus.CAPTURED;
  return PaymentSessionStatus.PENDING;
}

export class StorefrontPeachPaymentProvider extends AbstractPaymentProvider {
  static identifier = "peach";

  constructor(container: Record<string, unknown>, config: Record<string, unknown> = {}) {
    super(container, config);
  }

  async initiatePayment(input: InitiatePaymentInput): Promise<InitiatePaymentOutput> {
    const config = peachPaymentConfig();
    if (!config) throw new Error("Peach sandbox checkout is not configured");
    const sessionId = input.context?.idempotency_key;
    const amountMinor = medusaAmountToMinor(input.amount);
    const currency = input.currency_code.toUpperCase();
    if (!sessionId || !/^[A-Z]{3}$/.test(currency) || amountMinor === null || amountMinor <= 0) {
      throw new Error("Peach checkout requires a valid Medusa payment session, currency, and amount");
    }

    const db = this.db();
    const existing = await findPeachAttemptBySession(db, sessionId);
    if (existing) return this.existingAttempt(existing);

    // Authentication happens before the durable attempt because no payment has
    // been created yet. Persist the unique reference before the checkout POST.
    const { token } = await peachAccessToken(config);
    const { attempt, created } = await createPeachAttempt(db, {
      paymentSessionId: sessionId, amountMinor, currencyCode: currency,
    });
    if (!created) return this.existingAttempt(attempt);

    const returnUrl = `${config.storefrontUrl}/checkout/peach-return`;
    let response: Response;
    try {
      response = await fetch(`${config.checkoutBaseUrl}/v2/checkout`, {
        method: "POST",
        headers: {
          accept: "application/json",
          authorization: `Bearer ${token}`,
          "content-type": "application/json",
          referer: new URL(config.storefrontUrl).origin,
        },
        body: JSON.stringify({
          authentication: { entityId: config.entityId },
          merchantTransactionId: attempt.merchant_reference,
          amount: minorToMajor(attempt.amount_minor),
          currency: attempt.currency_code,
          paymentType: "DB",
          nonce: attempt.nonce,
          shopperResultUrl: returnUrl,
          notificationUrl: config.webhookUrl,
        }),
        signal: AbortSignal.timeout(15_000),
        cache: "no-store",
      });
    } catch {
      await updatePeachAttempt(db, attempt.id, { status: "initiation_unknown" });
      return this.pendingOutput(attempt, "initiation_unknown");
    }

    if (!response.ok) {
      if (response.status >= 500 || response.status === 429) {
        await updatePeachAttempt(db, attempt.id, { status: "initiation_unknown" });
        return this.pendingOutput(attempt, "initiation_unknown");
      }
      await updatePeachAttempt(db, attempt.id, { status: "declined" });
      return {
        id: attempt.merchant_reference,
        status: PaymentSessionStatus.ERROR,
        data: this.sessionData(attempt, "declined"),
      };
    }

    let body: Record<string, unknown>;
    try { body = await response.json() as Record<string, unknown>; }
    catch {
      await updatePeachAttempt(db, attempt.id, { status: "initiation_unknown" });
      return this.pendingOutput(attempt, "initiation_unknown");
    }
    const checkoutId = typeof body.checkoutId === "string" ? body.checkoutId : "";
    const redirectUrl = typeof body.redirectUrl === "string" ? body.redirectUrl : "";
    const knownCheckoutId = /^[A-Za-z0-9._-]{1,64}$/.test(checkoutId);
    if (knownCheckoutId) {
      await updatePeachAttempt(db, attempt.id, { checkout_id: checkoutId, status: "initiation_unknown" });
    }
    if (!knownCheckoutId || !redirectUrl || !this.isPeachRedirect(redirectUrl, config.checkoutBaseUrl)) {
      await updatePeachAttempt(db, attempt.id, { status: "initiation_unknown" });
      return this.pendingOutput(attempt, "initiation_unknown", knownCheckoutId ? { checkout_id: checkoutId } : {});
    }
    await updatePeachAttempt(db, attempt.id, { checkout_id: checkoutId, redirect_url: redirectUrl, status: "checkout_created" });
    return {
      id: checkoutId,
      status: PaymentSessionStatus.PENDING,
      data: this.sessionData(attempt, "checkout_created", { checkout_id: checkoutId, redirect_url: redirectUrl }),
    };
  }

  async authorizePayment(input: AuthorizePaymentInput): Promise<AuthorizePaymentOutput> {
    const attempt = await this.requireVerifiedCapturedAttempt(input.data, input.context?.idempotency_key);
    return {
      // Peach DB has already captured the payment when its verified success
      // event reaches this workflow. CAPTURED makes Medusa record its native
      // capture without sending a second capture request to Peach.
      status: PaymentSessionStatus.CAPTURED,
      data: {
        ...(input.data || {}),
        peach_status: "captured",
        peach_authorized_payment_session_id: attempt.payment_session_id,
        ...(typeof input.data?.peach_transaction_id === "string" ? { transaction_id: input.data.peach_transaction_id } : {}),
        ...(typeof input.data?.peach_checkout_id === "string" ? { provider_payment_id: input.data.peach_checkout_id } : {}),
      },
    };
  }

  async capturePayment(_input: CapturePaymentInput): Promise<CapturePaymentOutput> {
    throw new Error("Separate Peach capture is unsupported; use verified hosted checkout");
  }

  async getPaymentStatus(input: GetPaymentStatusInput): Promise<GetPaymentStatusOutput> {
    return { status: peachPaymentSessionStatus(input.data?.peach_status) };
  }

  async retrievePayment(input: RetrievePaymentInput): Promise<RetrievePaymentOutput> { return { data: input.data || {} }; }
  async updatePayment(input: UpdatePaymentInput): Promise<UpdatePaymentOutput> { return { data: input.data || {}, status: PaymentSessionStatus.PENDING }; }
  async deletePayment(_input: DeletePaymentInput): Promise<DeletePaymentOutput> { return { data: NO_DATA }; }
  async refundPayment(_input: RefundPaymentInput): Promise<RefundPaymentOutput> { throw new Error("Peach refunds are not enabled for this storefront"); }
  async cancelPayment(input: CancelPaymentInput): Promise<CancelPaymentOutput> {
    return { data: { ...(input.data || {}), provider: "peach" } };
  }

  async getWebhookActionAndData(input: ProviderWebhookPayload["payload"]): Promise<WebhookActionResult> {
    const event = input.data as Record<string, unknown>;
    const merchantReference = typeof event.merchant_reference === "string" ? event.merchant_reference : "";
    const attempt = merchantReference ? await findPeachAttemptByReference(this.db(), merchantReference) : undefined;
    if (!attempt) return { action: PaymentActions.NOT_SUPPORTED };

    const amountMinor = typeof event.amount_minor === "number" ? event.amount_minor : null;
    const checkoutId = typeof event.checkout_id === "string" ? event.checkout_id : "";
    const currency = typeof event.currency_code === "string" ? event.currency_code : "";
    const paymentType = typeof event.payment_type === "string" ? event.payment_type : "";
    if (!Number.isSafeInteger(amountMinor) || amountMinor !== Number(attempt.amount_minor) || currency !== attempt.currency_code || paymentType !== "DB" ||
      (attempt.checkout_id && checkoutId !== attempt.checkout_id)) {
      return { action: PaymentActions.NOT_SUPPORTED };
    }

    const state = peachResultState(event.result_code, paymentType);
    const action = state === "paid" ? PaymentActions.SUCCESSFUL
      : state === "pending" || state === "unknown" ? PaymentActions.PENDING
      : state === "declined" ? PaymentActions.FAILED
      : state === "cancelled" ? PaymentActions.CANCELED
      : PaymentActions.NOT_SUPPORTED;
    if (action === PaymentActions.NOT_SUPPORTED) return { action };
    return {
      action,
      data: {
        session_id: attempt.payment_session_id,
        amount: minorToMajor(Number(attempt.amount_minor)),
      },
    };
  }

  private db(): Knex {
    return this.container[ContainerRegistrationKeys.PG_CONNECTION] as Knex;
  }

  private async requireVerifiedCapturedAttempt(data: Record<string, unknown> | undefined, sessionId: string | undefined): Promise<PeachAttempt> {
    const merchantReference = typeof data?.peach_merchant_reference === "string" ? data.peach_merchant_reference : "";
    const attempt = merchantReference ? await findPeachAttemptByReference(this.db(), merchantReference) : undefined;
    const checkoutId = typeof data?.peach_checkout_id === "string" ? data.peach_checkout_id
      : typeof data?.checkout_id === "string" ? data.checkout_id : "";
    const amountMinor = typeof data?.peach_amount_minor === "number" ? data.peach_amount_minor : null;
    const isPaidSessionData = data?.peach_status === "paid" || data?.peach_status === "captured";
    if (!attempt || !sessionId || attempt.payment_session_id !== sessionId || attempt.status !== "captured" ||
      attempt.last_event_state !== "paid" || !isPaidSessionData || amountMinor !== Number(attempt.amount_minor) ||
      data?.currency_code !== attempt.currency_code || (attempt.checkout_id && checkoutId !== attempt.checkout_id)) {
      throw new Error("Peach payment is not verified as captured for this payment session");
    }
    return attempt;
  }

  private existingAttempt(attempt: Awaited<ReturnType<typeof findPeachAttemptBySession>>): InitiatePaymentOutput {
    if (!attempt) throw new Error("Peach payment attempt could not be recovered");
    const state = attempt.status === "checkout_created" ? "checkout_created" : "initiation_unknown";
    return {
      id: attempt.checkout_id || attempt.merchant_reference,
      status: PaymentSessionStatus.PENDING,
      data: this.sessionData(attempt, state, {
        ...(attempt.checkout_id ? { checkout_id: attempt.checkout_id } : {}),
        ...(attempt.redirect_url ? { redirect_url: attempt.redirect_url } : {}),
      }),
    };
  }

  private pendingOutput(attempt: { id: string; merchant_reference: string; amount_minor: number; currency_code: string }, state: string, extra: Record<string, unknown> = {}): InitiatePaymentOutput {
    return { id: attempt.merchant_reference, status: PaymentSessionStatus.PENDING, data: this.sessionData(attempt, state, extra) };
  }

  private sessionData(attempt: { merchant_reference: string; amount_minor: number; currency_code: string }, state: string, extra: Record<string, unknown> = {}): Record<string, unknown> {
    return {
      peach_status: state,
      peach_merchant_reference: attempt.merchant_reference,
      peach_amount_minor: Number(attempt.amount_minor),
      currency_code: attempt.currency_code,
      ...extra,
    };
  }

  private isPeachRedirect(value: string, base: string): boolean {
    try { return new URL(value).origin === new URL(base).origin; }
    catch { return false; }
  }
}
