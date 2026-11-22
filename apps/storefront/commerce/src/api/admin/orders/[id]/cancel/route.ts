import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import type { AuthenticatedMedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import type { HttpTypes } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, MedusaError } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { withStorefrontRefundWriter } from "../../../../../refund-cutover";

type CancelOrderRequest = AuthenticatedMedusaRequest<unknown, HttpTypes.AdminGetOrderParams>;
type CancelOrderResponse = MedusaResponse<HttpTypes.AdminOrderResponse>;
type CancelOrderHandler = (req: CancelOrderRequest, res: CancelOrderResponse) => Promise<void>;

const requireMedusa = createRequire(__filename);
const medusaDirectory = dirname(requireMedusa.resolve("@medusajs/medusa/package.json"));
const { POST: cancelOrder } = requireMedusa(join(medusaDirectory, "dist/api/admin/orders/[id]/cancel/route.js")) as {
  POST: CancelOrderHandler;
};

if (typeof cancelOrder !== "function") {
  throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "The native Medusa order cancellation handler has changed");
}

export async function POST(req: CancelOrderRequest, res: CancelOrderResponse): Promise<void> {
  const db = req.scope.resolve<Knex>(ContainerRegistrationKeys.PG_CONNECTION);
  // Native cancellation may proceed after a failed batch refund. Admit the
  // enclosing workflow before it updates the order or releases reservations.
  await withStorefrontRefundWriter(db, { operation: "admin_cancel", referenceId: req.params.id },
    () => cancelOrder(req, res));
}
