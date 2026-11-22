import { AsyncLocalStorage } from "node:async_hooks";
import { randomUUID } from "node:crypto";
import { MedusaError } from "@medusajs/framework/utils";
import type { Knex } from "knex";

const gateId = "medusa-refunds";
const gateTable = "storefront_refund_cutover";
const writerTable = "storefront_refund_writer";
const deferredCode = "storefront_refunds_temporarily_deferred";
const currentWriter = new AsyncLocalStorage<{ db: Knex; active: boolean }>();

function refundDeferred(): MedusaError {
  return new MedusaError(
    MedusaError.Types.NOT_ALLOWED,
    "Refund processing is temporarily deferred. Try again after the update.",
    deferredCode,
  );
}

export function isStorefrontRefundDeferred(error: unknown): boolean {
  return typeof error === "object" && error !== null && "code" in error && error.code === deferredCode;
}

type WriterReference = {
  operation: "native_refund" | "admin_cancel" | "paystack_dispatch" | "paystack_reconcile";
  referenceId: string;
};

export async function withStorefrontRefundWriter<T>(
  db: Knex, reference: WriterReference, operation: () => Promise<T>,
): Promise<T> {
  // The admitted Admin cancellation handler awaits its native refund steps.
  // Those steps share the same admission, including after cutover closes.
  const current = currentWriter.getStore();
  if (current?.db === db && current.active) return operation();

  const writerId = randomUUID();
  try {
    await db.transaction(async (tx) => {
      // Cutover takes an exclusive lock on the same row. Closing the gate
      // either sees this committed writer or prevents its admission entirely.
      const gate = await tx<{ id: string; phase: string }>(gateTable)
        .where({ id: gateId })
        .forShare()
        .first("phase");
      if (gate?.phase !== "legacy_open") throw refundDeferred();
      await tx(writerTable).insert({ id: writerId, operation: reference.operation, reference_id: reference.referenceId });
    });
  } catch (error) {
    if (isStorefrontRefundDeferred(error)) throw error;

    // The INSERT may have committed even if the connection failed to report
    // it. An unacknowledged admission stays durable and never starts a refund.
    console.warn("Could not admit a storefront refund writer", { writerId });
    throw refundDeferred();
  }

  const writer = { db, active: true };
  try {
    return await currentWriter.run(writer, operation);
  } finally {
    writer.active = false;
    try {
      await db(writerTable).where({ id: writerId }).delete();
    } catch {
      // An interrupted cleanup keeps the writer visible to cutover. Preserve
      // the operation's outcome so this cannot invite a second provider call.
      console.warn("Could not release a storefront refund writer", { writerId });
    }
  }
}
