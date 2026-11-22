import { randomUUID } from "node:crypto";
import knexFactory, { type Knex } from "knex";
import { Migration20261122153000 } from "./modules/storefront-refund-cutover/migrations/Migration20261122153000";
import { isStorefrontRefundDeferred, withStorefrontRefundWriter } from "./refund-cutover";

const databaseUrl = process.env.STOREFRONT_PG_TEST_URL;
const describeWithPostgres = databaseUrl ? describe : describe.skip;
const gateTable = "storefront_refund_cutover";
const writerTable = "storefront_refund_writer";
const gateId = "medusa-refunds";
const sample = { operation: "native_refund", referenceId: "pay_fixture" } as const;

function barrier() {
  let signal!: () => void;
  const wait = new Promise<void>(resolve => { signal = () => resolve(); });
  return { wait, signal };
}

describeWithPostgres("Storefront refund cutover admission (isolated PostgreSQL)", () => {
  let admin: Knex;
  let db: Knex;
  const schema = `storefront_refund_gate_${randomUUID().replaceAll("-", "")}`;

  beforeAll(async () => {
    if (!databaseUrl || !["localhost", "127.0.0.1", "[::1]"].includes(new URL(databaseUrl).hostname)) {
      throw new Error("Refund cutover integration tests require a loopback PostgreSQL fixture.");
    }
    admin = knexFactory({ client: "pg", connection: databaseUrl });
    await admin.raw("CREATE SCHEMA ??", [schema]);
    db = knexFactory({ client: "pg", connection: databaseUrl, searchPath: [schema] });
    const statements: string[] = [];
    const migration: Migration20261122153000 = Object.create(Migration20261122153000.prototype);
    Reflect.set(migration, "addSql", (statement: string) => statements.push(statement));
    await migration.up();
    await db.transaction(async tx => {
      for (const statement of statements) await tx.raw(statement);
    });
  });

  beforeEach(async () => {
    await db(writerTable).delete();
    await db(gateTable).insert({ id: gateId, phase: "legacy_open" }).onConflict("id").merge();
  });

  afterAll(async () => {
    if (db) await db.destroy();
    if (admin) {
      try { await admin.raw("DROP SCHEMA ?? CASCADE", [schema]); }
      finally { await admin.destroy(); }
    }
  });

  test("publishes a durable admission before calling the writer and removes it after settlement", async () => {
    await expect(withStorefrontRefundWriter(db, sample, async () => {
      expect(await db(writerTable).select("id", "admitted_at", "operation", "reference_id")).toEqual([
        { id: expect.any(String), admitted_at: expect.any(Date), operation: "native_refund", reference_id: "pay_fixture" },
      ]);
      return "refund result";
    })).resolves.toBe("refund result");
    expect(await db(writerTable)).toEqual([]);

    const failure = new Error("native refund rejected");
    await expect(withStorefrontRefundWriter(db, sample, async () => { throw failure; })).rejects.toBe(failure);
    expect(await db(writerTable)).toEqual([]);
  });

  test("cutover sees the active writer and denies any later one while draining", async () => {
    const admitted = barrier();
    const settle = barrier();
    const writer = withStorefrontRefundWriter(db, sample, async () => {
      admitted.signal();
      await settle.wait;
      return withStorefrontRefundWriter(db, sample, async () => {
        expect(await db(writerTable)).toHaveLength(1);
        return "existing writer finished";
      });
    });

    try {
      await Promise.race([admitted.wait, writer]);
      await db(gateTable).where({ id: gateId }).update({ phase: "legacy_closed" });
      expect(await db(writerTable)).toHaveLength(1);
      const lateWriter = jest.fn(async () => "late writer ran");
      await expect(withStorefrontRefundWriter(db, sample, lateWriter)).rejects.toMatchObject({
        code: "storefront_refunds_temporarily_deferred",
      });
      expect(lateWriter).not.toHaveBeenCalled();
    } finally {
      settle.signal();
      await expect(writer).resolves.toBe("existing writer finished");
    }

    expect(await db(writerTable)).toEqual([]);
  });

  test("a close holding the gate row lock prevents a racing admission", async () => {
    const closer = await db.transaction();
    const operation = jest.fn(async () => "racing writer ran");
    try {
      await closer(gateTable).where({ id: gateId }).update({ phase: "legacy_closed" });
      const admission = withStorefrontRefundWriter(db, sample, operation);
      const rejected = expect(admission).rejects.toMatchObject({ code: "storefront_refunds_temporarily_deferred" });
      await closer.commit();
      await rejected;
      expect(operation).not.toHaveBeenCalled();
      expect(await db(writerTable)).toEqual([]);
    } finally {
      if (!closer.isCompleted()) await closer.rollback();
    }
  });

  test("missing and upgraded gate rows both remain closed to the legacy writer", async () => {
    const operation = jest.fn(async () => "writer ran");
    await db(gateTable).where({ id: gateId }).update({ phase: "upgrade_ready" });
    await expect(withStorefrontRefundWriter(db, sample, operation).catch(isStorefrontRefundDeferred)).resolves.toBe(true);

    await db(gateTable).where({ id: gateId }).delete();
    await expect(withStorefrontRefundWriter(db, sample, operation).catch(isStorefrontRefundDeferred)).resolves.toBe(true);
    expect(operation).not.toHaveBeenCalled();
    expect(await db(writerTable)).toEqual([]);
  });

  test("leaves the admission visible after cleanup fails and preserves the completed refund outcome", async () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    await db.raw(`
      CREATE FUNCTION deny_refund_writer_cleanup() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        RAISE EXCEPTION 'disposable fixture rejects admission cleanup';
      END;
      $$;
      CREATE TRIGGER deny_refund_writer_cleanup BEFORE DELETE ON storefront_refund_writer
        FOR EACH ROW EXECUTE FUNCTION deny_refund_writer_cleanup();
    `);
    try {
      await expect(withStorefrontRefundWriter(db, sample, async () => "completed refund")).resolves.toBe("completed refund");
      expect(await db(writerTable)).toHaveLength(1);
      expect(warn).toHaveBeenCalledWith("Could not release a storefront refund writer", { writerId: expect.any(String) });
    } finally {
      warn.mockRestore();
      await db.raw("DROP TRIGGER deny_refund_writer_cleanup ON storefront_refund_writer");
      await db.raw("DROP FUNCTION deny_refund_writer_cleanup()");
    }
  });
});
