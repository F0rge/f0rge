import { randomUUID } from "node:crypto";
import type {
  AuthorizePaymentInput,
  AuthorizePaymentOutput,
  CancelPaymentInput,
  CancelPaymentOutput,
  CapturePaymentInput,
  CapturePaymentOutput,
  DeletePaymentInput,
  DeletePaymentOutput,
  GetPaymentStatusInput,
  GetPaymentStatusOutput,
  InitiatePaymentInput,
  InitiatePaymentOutput,
  ProviderWebhookPayload,
  RefundPaymentInput,
  RefundPaymentOutput,
  RetrievePaymentInput,
  RetrievePaymentOutput,
  UpdatePaymentInput,
  UpdatePaymentOutput,
  WebhookActionResult,
} from "@medusajs/framework/types";
import { AbstractPaymentProvider, PaymentActions, PaymentSessionStatus } from "@medusajs/framework/utils";

const outcomes = {
  success: PaymentActions.SUCCESSFUL,
  pending: PaymentActions.PENDING,
  declined: PaymentActions.FAILED,
  cancelled: PaymentActions.CANCELED,
} as const;

type TestOutcome = keyof typeof outcomes;

export class StorefrontTestPaymentProvider extends AbstractPaymentProvider {
  static identifier = "storefront-test";

  constructor(container: Record<string, unknown>, config: Record<string, unknown> = {}) {
    super(container, config);
  }

  async initiatePayment(input: InitiatePaymentInput): Promise<InitiatePaymentOutput> {
    return {
      id: randomUUID(),
      status: PaymentSessionStatus.PENDING,
      data: { test_provider: true, amount: input.amount, currency_code: input.currency_code },
    };
  }

  async authorizePayment(_input: AuthorizePaymentInput): Promise<AuthorizePaymentOutput> {
    return { status: PaymentSessionStatus.AUTHORIZED, data: { test_provider: true } };
  }

  async capturePayment(_input: CapturePaymentInput): Promise<CapturePaymentOutput> {
    return { data: { test_provider: true, captured: true } };
  }

  async getPaymentStatus(input: GetPaymentStatusInput): Promise<GetPaymentStatusOutput> {
    const outcome = input.data?.outcome;
    const status = outcome === "success" ? PaymentSessionStatus.CAPTURED
      : outcome === "declined" ? PaymentSessionStatus.ERROR
      : outcome === "cancelled" ? PaymentSessionStatus.CANCELED
      : PaymentSessionStatus.PENDING;
    return { status };
  }

  async retrievePayment(input: RetrievePaymentInput): Promise<RetrievePaymentOutput> {
    return { data: input.data || {} };
  }

  async updatePayment(input: UpdatePaymentInput): Promise<UpdatePaymentOutput> {
    return { data: input.data || {}, status: PaymentSessionStatus.PENDING };
  }

  async deletePayment(_input: DeletePaymentInput): Promise<DeletePaymentOutput> { return { data: {} }; }
  async refundPayment(_input: RefundPaymentInput): Promise<RefundPaymentOutput> { return { data: { test_provider: true } }; }
  async cancelPayment(_input: CancelPaymentInput): Promise<CancelPaymentOutput> { return { data: { test_provider: true } }; }

  async getWebhookActionAndData(input: ProviderWebhookPayload["payload"]): Promise<WebhookActionResult> {
    const event = input.data;
    const sessionId = event.session_id;
    const amount = event.amount;
    const outcome = event.outcome;
    if (typeof sessionId !== "string" || typeof amount !== "number" ||
      typeof outcome !== "string" || !(outcome in outcomes)) {
      return { action: PaymentActions.NOT_SUPPORTED };
    }
    return {
      action: outcomes[outcome as TestOutcome],
      data: { session_id: sessionId, amount },
    };
  }
}
