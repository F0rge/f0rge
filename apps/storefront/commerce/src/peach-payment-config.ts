export type PeachPaymentEnvironment = Record<string, string | undefined>;

export const PEACH_PAYMENT_PROVIDER_ID = "pp_peach_sandbox";

export type PeachPaymentConfig = {
  clientId: string;
  clientSecret: string;
  merchantId: string;
  entityId: string;
  webhookSecret: string;
  checkoutBaseUrl: string;
  authBaseUrl: string;
  webhookUrl: string;
  storefrontUrl: string;
};

const SANDBOX_CHECKOUT_URL = "https://testsecure.peachpayments.com";
const SANDBOX_AUTH_URL = "https://sandbox-dashboard.peachpayments.com";
const ENV_FIELDS = [
  "PEACH_CLIENT_ID",
  "PEACH_CLIENT_SECRET",
  "PEACH_MERCHANT_ID",
  "PEACH_ENTITY_ID",
  "PEACH_WEBHOOK_SECRET",
  "PEACH_WEBHOOK_URL",
] as const;

/** Classic Peach Checkout V2 is deliberately sandbox-only in this release. */
export function peachPaymentConfig(env: PeachPaymentEnvironment = process.env): PeachPaymentConfig | null {
  const configured = ENV_FIELDS.filter((key) => Boolean(env[key]?.trim()));
  if (configured.length === 0) return null;
  if (configured.length !== ENV_FIELDS.length) {
    throw new Error("Peach sandbox checkout configuration is incomplete");
  }
  if (env.PEACH_ENVIRONMENT !== "sandbox") {
    throw new Error("Peach checkout is sandbox-only; set PEACH_ENVIRONMENT=sandbox");
  }

  const webhookUrl = env.PEACH_WEBHOOK_URL!.trim();
  const storefrontUrl = (env.STOREFRONT_PUBLIC_URL || "http://localhost:3004").trim();
  assertAllowedUrl(webhookUrl, env);
  assertAllowedUrl(storefrontUrl, env);
  const callback = new URL(webhookUrl);
  if (callback.pathname !== "/hooks/peach" || callback.search) {
    throw new Error("Peach callback URL must target the isolated /hooks/peach route without query parameters");
  }
  return {
    clientId: env.PEACH_CLIENT_ID!.trim(),
    clientSecret: env.PEACH_CLIENT_SECRET!.trim(),
    merchantId: env.PEACH_MERCHANT_ID!.trim(),
    entityId: env.PEACH_ENTITY_ID!.trim(),
    webhookSecret: env.PEACH_WEBHOOK_SECRET!.trim(),
    checkoutBaseUrl: SANDBOX_CHECKOUT_URL,
    authBaseUrl: SANDBOX_AUTH_URL,
    webhookUrl,
    storefrontUrl: storefrontUrl.replace(/\/$/, ""),
  };
}

export function peachPaymentEnabled(env: PeachPaymentEnvironment = process.env): boolean {
  return peachPaymentConfig(env) !== null;
}

function assertAllowedUrl(value: string, env: PeachPaymentEnvironment): void {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error("Peach sandbox checkout URLs must be valid absolute URLs");
  }
  const isLocal = ["localhost", "127.0.0.1", "::1"].includes(url.hostname);
  if (url.protocol !== "https:" && !(isLocal && env.NODE_ENV !== "production" && url.protocol === "http:")) {
    throw new Error("Peach sandbox checkout URLs must use HTTPS outside local development");
  }
  if (url.username || url.password || url.hash) {
    throw new Error("Peach sandbox checkout URLs cannot contain credentials or fragments");
  }
}
