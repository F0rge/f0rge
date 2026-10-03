import { verifiedStorefrontCustomer } from "./storefront-order-claims";

describe("verified Storefront customer claim context", () => {
  const previousIssuer = process.env.STOREFRONT_CLERK_ISSUER;
  beforeEach(() => { process.env.STOREFRONT_CLERK_ISSUER = "https://clerk.example"; });
  afterAll(() => {
    if (previousIssuer === undefined) delete process.env.STOREFRONT_CLERK_ISSUER;
    else process.env.STOREFRONT_CLERK_ISSUER = previousIssuer;
  });

  const valid = {
    actor_type: "customer",
    actor_id: "cus_verified",
    auth_identity_id: "auth_123",
    auth_provider: "storefront-clerk",
    user_metadata: {
      email: "Ada@example.com",
      email_verified: true,
      clerk_issuer: "https://clerk.example",
      clerk_subject: "user_123",
    },
  };

  it("accepts only a signed customer context from the configured verified Clerk provider", () => {
    expect(verifiedStorefrontCustomer(valid)).toEqual({
      id: "cus_verified", authIdentityId: "auth_123", email: "ada@example.com", issuer: "https://clerk.example", subject: "user_123",
    });
    expect(verifiedStorefrontCustomer({ ...valid, auth_provider: "emailpass" })).toBeNull();
    expect(verifiedStorefrontCustomer({ ...valid, actor_type: "user" })).toBeNull();
    expect(verifiedStorefrontCustomer({ ...valid, user_metadata: { ...valid.user_metadata, email_verified: false } })).toBeNull();
    expect(verifiedStorefrontCustomer({ ...valid, user_metadata: { ...valid.user_metadata, clerk_issuer: "https://other.example" } })).toBeNull();
    expect(verifiedStorefrontCustomer({ ...valid, user_metadata: { ...valid.user_metadata, clerk_subject: "" } })).toBeNull();
  });

  it("fails closed when the expected Clerk issuer is not configured", () => {
    delete process.env.STOREFRONT_CLERK_ISSUER;
    expect(verifiedStorefrontCustomer(valid)).toBeNull();
  });
});
