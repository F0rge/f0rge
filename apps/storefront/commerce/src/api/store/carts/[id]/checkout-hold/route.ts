import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { cancelCheckoutHold, startCheckoutHold } from "../../../../../checkout-holds";

export async function POST(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  const hold = await startCheckoutHold(req.scope, req.params.id);
  res.status(hold.status === "active" ? 200 : 409).json({ hold });
}

export async function DELETE(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  const hold = await cancelCheckoutHold(req.scope, req.params.id);
  res.json({ hold });
}
