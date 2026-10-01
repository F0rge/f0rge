import { sign, generateKeyPairSync } from "node:crypto";
import type { AuthIdentityDTO, AuthIdentityProviderService } from "@medusajs/framework/types";
import { MedusaError } from "@medusajs/framework/utils";
import { StorefrontClerkAuthProvider } from "./service";

const issuer = "https://unit-test.clerk.accounts.dev";
const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const jwtKey = publicKey.export({ type: "spki", format: "pem" }).toString();

function token(overrides: Record<string, unknown> = {}): string {
  const header = Buffer.from(JSON.stringify({ alg: "RS256", typ: "JWT", kid: "test-key" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({
    iss: issuer,
    sub: "user_clerk_123",
    aud: "storefront",
    azp: "http://localhost:3004",
    exp: Math.floor(Date.now() / 1000) + 120,
    email: "customer@example.com",
    email_verified: true,
    first_name: "Ada",
    last_name: "Lovelace",
    ...overrides,
  })).toString("base64url");
  const message = `${header}.${payload}`;
  return `${message}.${sign("RSA-SHA256", Buffer.from(message), privateKey).toString("base64url")}`;
}

function createIdentityService(existing?: AuthIdentityDTO): AuthIdentityProviderService {
  const missing = () => new MedusaError(MedusaError.Types.NOT_FOUND, "not found");
  const identity: AuthIdentityDTO = existing || {
    id: "auth_1",
    provider_identities: [{
      id: "pi_1",
      provider: "storefront-clerk",
      entity_id: `${issuer}|user_clerk_123`,
      provider_metadata: { issuer },
      user_metadata: { email: "customer@example.com" },
    }],
  };
  return {
    retrieve: jest.fn(async ({ entity_id }) => {
      if (entity_id !== `${issuer}|user_clerk_123` || !existing) throw missing();
      return identity;
    }),
    create: jest.fn(async () => identity),
    update: jest.fn(async () => identity),
    setState: jest.fn(),
    getState: jest.fn(),
  };
}

describe("Storefront Clerk auth provider", () => {
  const saved = {
    CLERK_SECRET_KEY: process.env.CLERK_SECRET_KEY,
    CLERK_JWT_KEY: process.env.CLERK_JWT_KEY,
    STOREFRONT_CLERK_ISSUER: process.env.STOREFRONT_CLERK_ISSUER,
    STOREFRONT_CLERK_AUDIENCE: process.env.STOREFRONT_CLERK_AUDIENCE,
    STOREFRONT_PUBLIC_URL: process.env.STOREFRONT_PUBLIC_URL,
  };

  beforeEach(() => {
    delete process.env.CLERK_SECRET_KEY;
    process.env.CLERK_JWT_KEY = jwtKey;
    process.env.STOREFRONT_CLERK_ISSUER = issuer;
    process.env.STOREFRONT_CLERK_AUDIENCE = "storefront";
    process.env.STOREFRONT_PUBLIC_URL = "http://localhost:3004";
  });

  afterAll(() => {
    for (const [name, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  });

  it("creates an issuer-and-subject identity from a Clerk-signed verified-email token", async () => {
    const identities = createIdentityService();
    const result = await new StorefrontClerkAuthProvider().authenticate({ body: { token: token() } }, identities);
    expect(result.success).toBe(true);
    expect(identities.create).toHaveBeenCalledWith(expect.objectContaining({
      entity_id: `${issuer}|user_clerk_123`,
      provider_metadata: { issuer },
      user_metadata: expect.objectContaining({ email: "customer@example.com", email_verified: true }),
    }));
  });

  it.each([
    ["issuer", { iss: "https://other.clerk.accounts.dev" }],
    ["audience", { aud: "another-app" }],
    ["expiry", { exp: Math.floor(Date.now() / 1000) - 30 }],
    ["unverified email", { email_verified: false }],
  ])("rejects a signed token with an invalid %s", async (_name, claims) => {
    const identities = createIdentityService();
    const result = await new StorefrontClerkAuthProvider().authenticate({ body: { token: token(claims) } }, identities);
    expect(result.success).toBe(false);
    expect(identities.create).not.toHaveBeenCalled();
  });

  it("does not create an identity when retrieval fails for a reason other than not found", async () => {
    const identities = createIdentityService();
    identities.retrieve = jest.fn(async () => { throw new Error("database unavailable"); });
    const result = await new StorefrontClerkAuthProvider().authenticate({ body: { token: token() } }, identities);
    expect(result.success).toBe(false);
    expect(identities.create).not.toHaveBeenCalled();
  });

  it("refreshes verified issuer, subject, and email after a concurrent identity-create conflict", async () => {
    const staleIdentity: AuthIdentityDTO = {
      id: "auth_1",
      provider_identities: [{
        id: "pi_1", provider: "storefront-clerk", entity_id: `${issuer}|user_clerk_123`,
        provider_metadata: { issuer }, user_metadata: { email: "old@example.com", email_verified: true },
      }],
    };
    const identities = createIdentityService(staleIdentity);
    const stale = await identities.retrieve({ entity_id: `${issuer}|user_clerk_123` });
    identities.create = jest.fn(async () => { throw new Error("unique conflict"); });
    identities.retrieve = jest.fn(async () => ({
      ...stale,
      provider_identities: stale.provider_identities?.map((identity) => ({
        ...identity,
        user_metadata: { email: "old@example.com", email_verified: true },
      })),
    }));
    const result = await new StorefrontClerkAuthProvider().authenticate({
      body: { token: token({ email: "fresh@example.com", first_name: "Fresh", email_verified: true }) },
    }, identities);
    expect(result.success).toBe(true);
    expect(identities.update).toHaveBeenCalledWith(`${issuer}|user_clerk_123`, expect.objectContaining({
      provider_metadata: { issuer },
      user_metadata: expect.objectContaining({
        email: "fresh@example.com", email_verified: true, clerk_issuer: issuer, clerk_subject: "user_clerk_123",
      }),
    }));
  });

  it("fails closed when Clerk verification configuration is missing", async () => {
    delete process.env.CLERK_JWT_KEY;
    const identities = createIdentityService();
    const result = await new StorefrontClerkAuthProvider().authenticate({ body: { token: token() } }, identities);
    expect(result.success).toBe(false);
    expect(identities.retrieve).not.toHaveBeenCalled();
  });
});
