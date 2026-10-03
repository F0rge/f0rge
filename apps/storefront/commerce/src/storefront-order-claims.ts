import { createHash } from "node:crypto";
import type { Knex } from "knex";

export type VerifiedStorefrontCustomer = {
  id: string;
  authIdentityId: string;
  email: string;
  issuer: string;
  subject: string;
};

export type StorefrontOrderSummary = {
  id: string;
  display_id: number;
  created_at: Date | string;
  currency_code: string;
  status: string;
};

const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function verifiedStorefrontCustomer(value: unknown): VerifiedStorefrontCustomer | null {
  if (!value || typeof value !== "object") return null;
  const context = value as Record<string, unknown>;
  const metadata = context.user_metadata;
  if (!metadata || typeof metadata !== "object") return null;
  const claims = metadata as Record<string, unknown>;
  const id = context.actor_id;
  const authIdentityId = context.auth_identity_id;
  const email = typeof claims.email === "string" ? claims.email.trim().toLowerCase() : "";
  const issuer = claims.clerk_issuer;
  const subject = claims.clerk_subject;
  const configuredIssuer = process.env.STOREFRONT_CLERK_ISSUER;
  if (context.actor_type !== "customer" || context.auth_provider !== "storefront-clerk" ||
    typeof id !== "string" || !/^cus_[A-Za-z0-9_-]+$/.test(id) ||
    typeof authIdentityId !== "string" || !authIdentityId ||
    claims.email_verified !== true || !validEmail.test(email) ||
    typeof configuredIssuer !== "string" || !configuredIssuer ||
    typeof issuer !== "string" || issuer !== configuredIssuer ||
    typeof subject !== "string" || !subject) return null;
  return { id, authIdentityId, email, issuer, subject };
}

export async function listClaimableGuestOrders(db: Knex, customer: VerifiedStorefrontCustomer): Promise<StorefrontOrderSummary[]> {
  return await db("order")
    .select("id", "display_id", "created_at", "currency_code", "status")
    .whereNull("customer_id")
    .where({ is_draft_order: false })
    .whereNull("deleted_at")
    .whereRaw("lower(btrim(email)) = ?", [customer.email])
    .whereRaw("metadata ->> 'storefront_claimable_version' = '1'")
    .whereRaw("metadata ->> 'storefront_confirmation_sha256' ~ '^[a-f0-9]{64}$'")
    .orderBy("created_at", "desc")
    .limit(20) as StorefrontOrderSummary[];
}

/**
 * Claims only an explicitly marked, newly-created guest order. The conditional
 * UPDATE is the serialization point: concurrent claims cannot both transition
 * the same order, and the metadata merge leaves the checkout/handoff snapshot
 * untouched.
 */
export async function claimGuestStorefrontOrder(
  db: Knex,
  orderId: string,
  customer: VerifiedStorefrontCustomer,
): Promise<"claimed" | "already_owned" | "not_available"> {
  const audit = {
    version: 1,
    source: "verified_clerk_email",
    customer_id: customer.id,
    auth_identity_id: customer.authIdentityId,
    issuer: customer.issuer,
    clerk_subject_sha256: createHash("sha256").update(customer.subject).digest("hex"),
    email_sha256: createHash("sha256").update(customer.email).digest("hex"),
  };
  const changed = await db("order")
    .where({ id: orderId, is_draft_order: false })
    .whereNull("customer_id")
    .whereNull("deleted_at")
    .whereRaw("lower(btrim(email)) = ?", [customer.email])
    .whereRaw("metadata ->> 'storefront_claimable_version' = '1'")
    .whereRaw("metadata ->> 'storefront_confirmation_sha256' ~ '^[a-f0-9]{64}$'")
    .update({
      customer_id: customer.id,
      metadata: db.raw(
        "COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('storefront_owner_claim', ?::jsonb || jsonb_build_object('claimed_at', timezone('utc', now())))",
        [JSON.stringify(audit)],
      ),
    }, ["id"]);
  if (changed.length) return "claimed";

  const current = await db("order").select("customer_id").where({ id: orderId }).whereNull("deleted_at").first();
  return current?.customer_id === customer.id ? "already_owned" : "not_available";
}
