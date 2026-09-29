import { timingSafeEqual } from "node:crypto";
import { defineMiddlewares, type MedusaNextFunction, type MedusaRequest, type MedusaResponse } from "@medusajs/framework/http";

export function requireStorefrontBff(req: MedusaRequest, res: MedusaResponse, next: MedusaNextFunction): void {
  const secret = process.env.STOREFRONT_BFF_SECRET;
  const supplied = req.headers["x-storefront-bff-secret"];
  if (!secret || secret.length < 32 || typeof supplied !== "string") {
    res.status(403).json({ message: "Cart access is restricted" });
    return;
  }
  const expected = Buffer.from(secret);
  const received = Buffer.from(supplied);
  if (expected.length !== received.length || !timingSafeEqual(expected, received)) {
    res.status(403).json({ message: "Cart access is restricted" });
    return;
  }
  next();
}

export default defineMiddlewares({ routes: [{
  matcher: "/store/carts*",
  middlewares: [requireStorefrontBff],
}, {
  matcher: "/store/orders/:id/storefront-status",
  middlewares: [requireStorefrontBff],
}] });
