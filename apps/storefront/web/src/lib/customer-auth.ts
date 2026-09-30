import "server-only";

import { auth } from "@clerk/nextjs/server";

const backendUrl = process.env.MEDUSA_BACKEND_URL || "http://localhost:9000";
const publishableKey = process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY;
const clerkTemplate = process.env.STOREFRONT_CLERK_JWT_TEMPLATE;

export type CustomerContext = {
  id: string;
  token: string;
  email: string;
  first_name: string;
  last_name: string;
};

export class CustomerAuthError extends Error {
  constructor(public status: number, message = "Customer account is unavailable") { super(message); }
}

export function clerkCustomerAuthConfigured(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY && clerkTemplate);
}

function decodePayload(token: string): Record<string, unknown> | null {
  try {
    const value = token.split(".")[1];
    return value ? JSON.parse(Buffer.from(value, "base64url").toString("utf8")) as Record<string, unknown> : null;
  } catch { return null; }
}

export async function customerMedusaFetch(context: Pick<CustomerContext, "token">, path: string, method = "GET", body?: unknown): Promise<{ status: number; payload: Record<string, unknown> }> {
  if (!publishableKey) throw new CustomerAuthError(503, "Customer account is unavailable");
  const response = await fetch(`${backendUrl}${path}`, {
    method,
    headers: {
      "x-publishable-api-key": publishableKey,
      authorization: `Bearer ${context.token}`,
      ...(body === undefined ? {} : { "content-type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  return { status: response.status, payload };
}

function readCustomer(payload: Record<string, unknown>, token: string): CustomerContext | null {
  const candidate = payload.customer as Record<string, unknown> | undefined;
  if (!candidate || typeof candidate.id !== "string" || !/^cus_[A-Za-z0-9_-]+$/.test(candidate.id)) return null;
  return {
    id: candidate.id,
    token,
    email: typeof candidate.email === "string" ? candidate.email : "",
    first_name: typeof candidate.first_name === "string" ? candidate.first_name : "",
    last_name: typeof candidate.last_name === "string" ? candidate.last_name : "",
  };
}

async function refreshCustomerToken(token: string): Promise<string> {
  const { status, payload } = await customerMedusaFetch({ token }, "/auth/token/refresh", "POST");
  if (status < 200 || status >= 300 || typeof payload.token !== "string") throw new CustomerAuthError(503);
  return payload.token;
}

/**
 * Exchange the current, server-verified Clerk session for a short-lived Medusa
 * customer token. The Medusa token remains server-only and is never cookie or
 * browser storage state.
 */
export async function getCustomerContext(): Promise<CustomerContext | null> {
  if (!clerkCustomerAuthConfigured() || !publishableKey) return null;
  const clerkSession = await auth();
  if (!clerkSession.userId) return null;
  const clerkToken = await clerkSession.getToken({ template: clerkTemplate });
  if (!clerkToken) throw new CustomerAuthError(401, "Sign in to access your customer account");
  const clerkClaims = decodePayload(clerkToken);
  if (clerkClaims?.sub !== clerkSession.userId) throw new CustomerAuthError(401, "Invalid customer session");

  const authResponse = await fetch(`${backendUrl}/auth/customer/storefront-clerk`, {
    method: "POST",
    headers: {
      "x-publishable-api-key": publishableKey,
      "x-storefront-bff-secret": process.env.STOREFRONT_BFF_SECRET || "",
      "content-type": "application/json",
    },
    body: JSON.stringify({ token: clerkToken }),
    cache: "no-store",
  });
  const authPayload = await authResponse.json().catch(() => ({})) as Record<string, unknown>;
  if (!authResponse.ok || typeof authPayload.token !== "string") {
    throw new CustomerAuthError(authResponse.status === 401 ? 401 : 503);
  }

  let medusaToken = authPayload.token;
  let me = await customerMedusaFetch({ token: medusaToken }, "/store/customers/me");
  let customer = readCustomer(me.payload, medusaToken);
  if (!customer && (me.status === 401 || me.status === 404)) {
    const identityClaims = decodePayload(medusaToken)?.user_metadata as Record<string, unknown> | undefined;
    const email = typeof identityClaims?.email === "string" ? identityClaims.email : "";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || identityClaims?.email_verified !== true) {
      throw new CustomerAuthError(401, "Verified customer profile is unavailable");
    }
    const create = await customerMedusaFetch({ token: medusaToken }, "/store/customers", "POST", {
      email,
      first_name: typeof identityClaims.first_name === "string" ? identityClaims.first_name : "",
      last_name: typeof identityClaims.last_name === "string" ? identityClaims.last_name : "",
    });
    // Refresh also makes the new customer actor ID available to subsequent
    // /store/customers/me and address routes. On a concurrent first sign-in,
    // a failed create is accepted only if this same identity can then read /me.
    medusaToken = await refreshCustomerToken(medusaToken);
    me = await customerMedusaFetch({ token: medusaToken }, "/store/customers/me");
    customer = readCustomer(me.payload, medusaToken);
    if ((!create || create.status < 200 || create.status >= 300) && !customer) throw new CustomerAuthError(503);
  }
  if (!customer) throw new CustomerAuthError(503);
  return customer;
}
