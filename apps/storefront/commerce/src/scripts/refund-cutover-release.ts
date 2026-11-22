import { setTimeout } from "node:timers/promises";
import { Client } from "@medusajs/framework/pg";
import { assertHostedCommerceConfig } from "../hosted-commerce-config";
import { refundCutoverSchema } from "../modules/storefront-refund-cutover/schema";

const gateId = "medusa-refunds";
const drainTimeoutMs = 60_000;
type Phase = "legacy_open" | "legacy_closed" | "upgrade_ready";

class CutoverError extends Error {}

async function gatePhase(db: Client, lock = false): Promise<Phase> {
  const result = await db.query<{ phase: Phase }>(
    `SELECT phase FROM storefront_refund_cutover WHERE id = $1 ${lock ? "FOR UPDATE" : ""}`,
    [gateId],
  );
  const phase = result.rows[0]?.phase;
  if (phase !== "legacy_open" && phase !== "legacy_closed" && phase !== "upgrade_ready") {
    throw new CutoverError("The DasKasas refund compatibility marker is missing or invalid.");
  }
  return phase;
}

async function closeLegacyWriters(db: Client): Promise<void> {
  // Commit the fence before waiting, so no new legacy writer can register.
  // FOR UPDATE waits for any short admission transaction already in progress.
  await db.query("BEGIN");
  try {
    // Also serialize the genuinely blank database case, where no gate row
    // exists yet to lock. Persist the marker before Medusa can create tables.
    await db.query("SELECT pg_advisory_xact_lock(1570911614, 1)");
    const schema = await db.query<{ has_gate: boolean; has_tables: boolean }>(`
      SELECT to_regclass('storefront_refund_cutover') IS NOT NULL AS has_gate,
        EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = current_schema()) AS has_tables
    `);
    if (!schema.rows[0].has_gate) {
      if (schema.rows[0].has_tables) {
        throw new CutoverError("Deploy the DasKasas refund compatibility image before migrating an existing database.");
      }
      for (const statement of refundCutoverSchema) await db.query(statement);
    }
    if (await gatePhase(db, true) === "legacy_open") {
      await db.query("UPDATE storefront_refund_cutover SET phase = 'legacy_closed' WHERE id = $1", [gateId]);
    }
    await db.query("COMMIT");
  } catch (error) {
    await db.query("ROLLBACK").catch(() => {});
    throw error;
  }

  const deadline = performance.now() + drainTimeoutMs;
  for (;;) {
    const writers = await db.query("SELECT 1 FROM storefront_refund_writer LIMIT 1");
    if (!writers.rowCount) return;
    if (performance.now() >= deadline) {
      throw new CutoverError("Legacy refund writers have not drained. Cutover remains closed until they settle or are reconciled.");
    }
    await setTimeout(250);
  }
}

async function markUpgradeReady(db: Client): Promise<void> {
  await db.query("BEGIN");
  try {
    if (await gatePhase(db, true) === "legacy_open") {
      throw new CutoverError("The legacy refund gate must be closed before the upgrade is marked ready.");
    }
    const schema = await db.query(`
      SELECT 1 FROM pg_attribute
      WHERE attrelid = to_regclass('refund') AND attname = 'status' AND NOT attisdropped
    `);
    const writers = await db.query("SELECT 1 FROM storefront_refund_writer LIMIT 1");
    if (!schema.rowCount || writers.rowCount) {
      throw new CutoverError("Refund migration or legacy writer drain is incomplete.");
    }
    await db.query("UPDATE storefront_refund_cutover SET phase = 'upgrade_ready' WHERE id = $1", [gateId]);
    await db.query("COMMIT");
  } catch (error) {
    await db.query("ROLLBACK").catch(() => {});
    throw error;
  }
}

async function main(): Promise<void> {
  const command = process.argv[2];
  assertHostedCommerceConfig(process.env);
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) throw new CutoverError("Database URL is required for refund cutover.");
  const db = new Client({ connectionString, connectionTimeoutMillis: 5_000, statement_timeout: 5_000 });
  try {
    await db.connect();
    // Commerce and its Medusa migrations use the public schema.
    await db.query("SET search_path TO public");
    switch (command) {
      case "close":
        await closeLegacyWriters(db);
        break;
      case "ready":
        await markUpgradeReady(db);
        break;
      case "assert-ready":
        if (await gatePhase(db) !== "upgrade_ready") {
          throw new CutoverError("Complete the DasKasas refund cutover before starting the upgraded commerce image.");
        }
        break;
      default:
        throw new CutoverError("Expected close, ready, or assert-ready for refund cutover.");
    }
  } finally {
    await db.end();
  }
}

main().catch((error: unknown) => {
  console.error(error instanceof CutoverError ? error.message : "DasKasas refund cutover could not access its database state.");
  process.exitCode = 1;
});
