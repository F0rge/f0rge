export type PaystackPaymentEnvironment = Record<string, string | undefined>;

export const PAYSTACK_PAYMENT_PROVIDER_ID = "pp_paystack_checkout";
export const PAYSTACK_API_URL = "https://api.paystack.co";
export const PAYSTACK_RETURN_PATH = "/checkout/paystack-return";

export type PaystackPaymentConfig = {
  secretKey: string;
  webhookSecret: string;
  mode: "test" | "live";
  storefrontUrl: string;
  callbackUrl: string;
  refundsPaused: boolean;
};

const ENV_FIELDS = ["PAYSTACK_SECRET_KEY", "PAYSTACK_WEBHOOK_SECRET"] as const;

/** Paystack stays disabled until every required server-side value is set. */
export function paystackPaymentConfig(env: PaystackPaymentEnvironment = process.env): PaystackPaymentConfig | null {
  const configured = ENV_FIELDS.filter((key) => Boolean(env[key]?.trim()));
  if (configured.length === 0) return null;
  if (configured.length !== ENV_FIELDS.length) {
    throw new Error("Paystack checkout configuration is incomplete");
  }
  const secretKey = env.PAYSTACK_SECRET_KEY!.trim();
  const mode = /^sk_test_[A-Za-z0-9]+$/.test(secretKey) ? "test"
    : /^sk_live_[A-Za-z0-9]+$/.test(secretKey) ? "live" : null;
  if (!mode) throw new Error("PAYSTACK_SECRET_KEY must be a Paystack secret key (sk_test_ or sk_live_)");
  if (mode === "live" && env.PAYSTACK_LIVE_ENABLED !== "true") {
    throw new Error("A live Paystack key needs PAYSTACK_LIVE_ENABLED=true");
  }
  const webhookSecret = env.PAYSTACK_WEBHOOK_SECRET!.trim();
  if (!/^whsec_\S+$/.test(webhookSecret)) {
    throw new Error("PAYSTACK_WEBHOOK_SECRET must be the Paystack webhook signing secret (whsec_)");
  }

  const storefrontUrl = (env.STOREFRONT_PUBLIC_URL || "http://localhost:3004").trim().replace(/\/$/, "");
  assertAllowedUrl(storefrontUrl, env, mode);
  return {
    secretKey,
    webhookSecret,
    mode,
    storefrontUrl,
    callbackUrl: `${storefrontUrl}${PAYSTACK_RETURN_PATH}`,
    // Incident switch: stop new refund POSTs while verified outcomes still converge.
    refundsPaused: env.PAYSTACK_REFUNDS_PAUSED === "true",
  };
}

export function paystackPaymentEnabled(env: PaystackPaymentEnvironment = process.env): boolean {
  return paystackPaymentConfig(env) !== null;
}

function assertAllowedUrl(value: string, env: PaystackPaymentEnvironment, mode: "test" | "live"): void {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error("Paystack checkout URLs must be valid absolute URLs");
  }
  const isLocal = ["localhost", "127.0.0.1", "::1"].includes(url.hostname);
  const localHttp = isLocal && mode === "test" && env.NODE_ENV !== "production" && url.protocol === "http:";
  if (url.protocol !== "https:" && !localHttp) {
    throw new Error("Paystack checkout URLs must use HTTPS outside local test-mode development");
  }
  if (url.username || url.password || url.hash || url.search) {
    throw new Error("Paystack checkout URLs cannot contain credentials, query parameters, or fragments");
  }
}
