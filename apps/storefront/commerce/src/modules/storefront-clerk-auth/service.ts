import { verifyToken } from "@clerk/backend";
import type { AuthIdentityProviderService, AuthenticationInput, AuthenticationResponse } from "@medusajs/framework/types";
import { AbstractAuthModuleProvider, MedusaError } from "@medusajs/framework/utils";

type ClerkClaims = Record<string, unknown> & { sub?: unknown; iss?: unknown; exp?: unknown; email?: unknown; email_verified?: unknown };

function text(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function isNotFound(error: unknown): boolean {
  return error instanceof MedusaError && error.type === MedusaError.Types.NOT_FOUND;
}

export class StorefrontClerkAuthProvider extends AbstractAuthModuleProvider {
  static identifier = "storefront-clerk";

  async authenticate(data: AuthenticationInput, identities: AuthIdentityProviderService): Promise<AuthenticationResponse> {
    const token = text(data.body?.token);
    const issuer = process.env.STOREFRONT_CLERK_ISSUER;
    const audience = process.env.STOREFRONT_CLERK_AUDIENCE;
    const secretKey = process.env.CLERK_SECRET_KEY;
    const jwtKey = process.env.CLERK_JWT_KEY;
    const siteOrigin = process.env.STOREFRONT_PUBLIC_URL;
    if (!token || !issuer || !audience || (!secretKey && !jwtKey) || !siteOrigin) {
      return { success: false, error: "Clerk customer sign-in is not configured" };
    }

    let claims: ClerkClaims;
    try {
      const verified = await verifyToken(token, {
        ...(secretKey ? { secretKey } : { jwtKey }),
        audience,
        authorizedParties: [new URL(siteOrigin).origin],
        clockSkewInMs: 5_000,
      });
      const result = verified as unknown as Record<string, unknown>;
      if (Array.isArray(result.errors)) return { success: false, error: "Invalid customer session" };
      const payload = result.data && typeof result.data === "object" ? result.data : result;
      claims = payload as ClerkClaims;
    } catch {
      return { success: false, error: "Invalid customer session" };
    }

    const subject = text(claims.sub);
    const email = text(claims.email)?.toLowerCase();
    const expiresAt = typeof claims.exp === "number" ? claims.exp : 0;
    if (claims.iss !== issuer || !subject || expiresAt <= Math.floor(Date.now() / 1000) ||
      !email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ||
      claims.email_verified !== true) {
      return { success: false, error: "Invalid customer session" };
    }

    // The issuer and Clerk subject form the stable provider identity. Email is
    // mutable profile data and is never used to find or link an existing account.
    const entityId = `${issuer}|${subject}`;
    let existing: { kind: "found"; authIdentity: Awaited<ReturnType<AuthIdentityProviderService["retrieve"]>> } | { kind: "error"; error: unknown };
    try {
      existing = { kind: "found", authIdentity: await identities.retrieve({ entity_id: entityId }) };
    } catch (error) {
      existing = { kind: "error", error };
    }
    if (existing.kind === "found") {
      const linkedIssuer = existing.authIdentity.provider_identities?.find((identity) => identity.entity_id === entityId)?.provider_metadata?.issuer;
      if (linkedIssuer !== issuer) return { success: false, error: "Invalid customer session" };
      try {
        const authIdentity = await identities.update(entityId, {
          provider_metadata: { issuer },
          user_metadata: {
            email,
            first_name: text(claims.first_name) || "",
            last_name: text(claims.last_name) || "",
            email_verified: true,
          },
        });
        return { success: true, authIdentity };
      } catch {
        return { success: false, error: "Customer sign-in could not be completed" };
      }
    }
    if (!isNotFound(existing.error)) return { success: false, error: "Customer sign-in could not be completed" };

    const userMetadata = {
      email,
      first_name: text(claims.first_name) || "",
      last_name: text(claims.last_name) || "",
      email_verified: true,
    };
    try {
      const authIdentity = await identities.create({
        entity_id: entityId,
        provider_metadata: { issuer },
        user_metadata: userMetadata,
      });
      return { success: true, authIdentity };
    } catch {
      // A parallel first sign-in can win the unique-identity insert. Retrieve
      // that exact issuer+subject after the conflict; never fall back to email.
      try {
        const authIdentity = await identities.retrieve({ entity_id: entityId });
        const linkedIssuer = authIdentity.provider_identities?.find((identity) => identity.entity_id === entityId)?.provider_metadata?.issuer;
        if (linkedIssuer !== issuer) return { success: false, error: "Invalid customer session" };
        return { success: true, authIdentity };
      } catch {
        return { success: false, error: "Customer sign-in could not be completed" };
      }
    }
  }

  async register(_data: AuthenticationInput): Promise<AuthenticationResponse> {
    return { success: false, error: "Use passwordless customer sign-in" };
  }

  async update(_data: Record<string, unknown>): Promise<AuthenticationResponse> {
    throw new MedusaError(MedusaError.Types.NOT_ALLOWED, "Clerk identity updates are managed by Clerk");
  }
}
