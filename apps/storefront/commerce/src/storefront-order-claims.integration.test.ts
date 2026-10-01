import knexFactory, { type Knex } from "knex";
import { randomUUID } from "node:crypto";
import type { VerifiedStorefrontCustomer } from "./storefront-order-claims";
import { claimGuestStorefrontOrder, listClaimableGuestOrders } from "./storefront-order-claims";
import { Migration20240219102530 } from "@medusajs/order/dist/migrations/Migration20240219102530";

const databaseUrl = process.env.STOREFRONT_PG_TEST_URL;
const describeWithPostgres = databaseUrl ? describe : describe.skip;

describeWithPostgres("Storefront guest order claim (Medusa Order migration + isolated PostgreSQL)", () => {
  let admin: Knex;
  let db: Knex;
  let schema: string;
  let claimableId: string;
  let legacyId: string;
  let noDigestId: string;
  let ownedId: string;
  let draftId: string;
  const snapshots = {
    contact: { name: "Original guest", email: "ada@example.com" },
    shipping_address: { address_1: "12 Original Road", city: "Johannesburg" },
    financial: { amount_minor: 12500, currency: "ZAR" },
    storefront_handoff_outbox: [{ state: "pending", immutable: true }],
  };
  const customer: VerifiedStorefrontCustomer = {
    id: "cus_verified_ada", authIdentityId: "auth_clerk_ada", email: "ada@example.com", issuer: "https://clerk.example", subject: "user_ada",
  };
  const competitor: VerifiedStorefrontCustomer = {
    id: "cus_verified_competitor", authIdentityId: "auth_clerk_competitor", email: "ada@example.com", issuer: "https://clerk.example", subject: "user_competitor",
  };

  beforeAll(async () => {
    admin = knexFactory({ client: "pg", connection: databaseUrl });
    schema = `storefront_claim_${randomUUID().replaceAll("-", "")}`;
    await admin.raw("CREATE SCHEMA ??", [schema]);
    db = knexFactory({ client: "pg", connection: databaseUrl, searchPath: [schema] });
    const migrationSql: string[] = [];
    const migrationCollector: Migration20240219102530 = Object.create(Migration20240219102530.prototype);
    Reflect.set(migrationCollector, "addSql", (statement: string) => migrationSql.push(statement));
    await migrationCollector.up();
    for (const statement of migrationSql) await db.raw(statement);
  });

  afterAll(async () => {
    if (db) await db.destroy();
    if (admin && schema) {
      await admin.raw("DROP SCHEMA ?? CASCADE", [schema]);
      await admin.destroy();
    }
  });

  beforeEach(async () => {
    claimableId = `order_claim_${randomUUID().replaceAll("-", "")}`;
    legacyId = `order_legacy_${randomUUID().replaceAll("-", "")}`;
    noDigestId = `order_nodigest_${randomUUID().replaceAll("-", "")}`;
    ownedId = `order_owned_${randomUUID().replaceAll("-", "")}`;
    draftId = `order_draft_${randomUUID().replaceAll("-", "")}`;
    const marker = {
      storefront_claimable_version: 1,
      storefront_confirmation_sha256: "a".repeat(64),
      storefront_checkout_sha256: "b".repeat(64),
      storefront_handoff_outbox: snapshots.storefront_handoff_outbox,
      storefront_order_snapshot: snapshots,
    };
    await db("order").insert([
      { id: claimableId, email: " Ada@Example.com ", currency_code: "zar", status: "completed", metadata: marker },
      { id: legacyId, email: "ada@example.com", currency_code: "zar", status: "completed", metadata: { storefront_order_snapshot: snapshots } },
      { id: noDigestId, email: "ada@example.com", currency_code: "zar", status: "completed", metadata: { ...marker, storefront_confirmation_sha256: null } },
      { id: ownedId, email: "ada@example.com", customer_id: "cus_someone_else", currency_code: "zar", status: "completed", metadata: marker },
      { id: draftId, email: "ada@example.com", currency_code: "zar", status: "draft", is_draft_order: true, metadata: marker },
    ]);
  });

  afterEach(async () => {
    await db("order").whereIn("id", [claimableId, legacyId, noDigestId, ownedId, draftId]).del();
  });

  test("only explicit new guest provenance is claimable; legacy and conflicting orders stay out", async () => {
    const candidates = await listClaimableGuestOrders(db, customer);
    expect(candidates.map((order) => order.id)).toContain(claimableId);
    expect(candidates.map((order) => order.id)).not.toEqual(expect.arrayContaining([legacyId, noDigestId, ownedId, draftId]));

    await expect(claimGuestStorefrontOrder(db, legacyId, customer)).resolves.toBe("not_available");
    await expect(claimGuestStorefrontOrder(db, ownedId, customer)).resolves.toBe("not_available");
  });

  test("concurrent attempts create one ownership audit and preserve every checkout snapshot", async () => {
    const outcomes = await Promise.all([
      claimGuestStorefrontOrder(db, claimableId, customer),
      claimGuestStorefrontOrder(db, claimableId, competitor),
    ]);
    expect(outcomes.filter((result) => result === "claimed")).toHaveLength(1);
    expect(outcomes.filter((result) => result === "not_available")).toHaveLength(1);

    const order = await db("order").where({ id: claimableId }).first();
    expect([customer.id, competitor.id]).toContain(order.customer_id);
    expect(order.email).toBe(" Ada@Example.com ");
    expect(order.metadata.storefront_order_snapshot).toEqual(snapshots);
    expect(order.metadata.storefront_handoff_outbox).toEqual(snapshots.storefront_handoff_outbox);
    expect(order.metadata.storefront_owner_claim).toMatchObject({
      version: 1,
      source: "verified_clerk_email",
      customer_id: order.customer_id,
      auth_identity_id: expect.any(String),
      clerk_subject_sha256: expect.any(String),
      email_sha256: expect.any(String),
    });
    expect(Object.keys(order.metadata).filter((key) => key === "storefront_owner_claim")).toHaveLength(1);
    await expect(claimGuestStorefrontOrder(db, claimableId, { ...customer, id: order.customer_id })).resolves.toBe("already_owned");
    expect((await db("order").where({ id: claimableId }).first()).metadata.storefront_owner_claim).toEqual(order.metadata.storefront_owner_claim);
  });
});
