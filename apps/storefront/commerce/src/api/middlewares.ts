import { timingSafeEqual } from "node:crypto";
import { defineMiddlewares, type MedusaNextFunction, type MedusaRequest, type MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";

export async function requireStorefrontBff(req: MedusaRequest, res: MedusaResponse, next: MedusaNextFunction): Promise<void> {
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
  res.setHeader("Cache-Control", "private, no-store, max-age=0");
  res.setHeader("X-Robots-Tag", "noindex, nofollow, noarchive");

  const pathname = (req.originalUrl || req.path || "").split("?")[0];
  // Order confirmation is guarded by its separate, cart-bound capability. It
  // must continue to work after customer logout without exposing the cart API.
  const cartMatch = /(?:^|\/)store\/carts\/(cart_[^/]+)(?:\/|$)/.exec(pathname);
  // This middleware also guards order-status routes, which use order IDs. Only
  // cart endpoints need the cart-ownership check below.
  if (!cartMatch || pathname.endsWith("/storefront-confirmation")) {
    next();
    return;
  }

  const customerId = req.headers["x-storefront-customer-id"];
  const attaching = pathname.endsWith("/storefront-customer");
  if (typeof customerId === "string" && !/^cus_[A-Za-z0-9_-]+$/.test(customerId)) {
    res.status(404).json({ message: "Bag not found" });
    return;
  }
  if (attaching && typeof customerId !== "string") {
    res.status(404).json({ message: "Bag not found" });
    return;
  }
  try {
    const query = req.scope.resolve(ContainerRegistrationKeys.QUERY);
    const { data } = await query.graph({ entity: "cart", fields: ["id", "customer_id"], filters: { id: cartMatch[1] } });
    const cart = data[0] as { id: string; customer_id?: string | null } | undefined;
    const allowed = cart && (typeof customerId !== "string"
      ? !attaching && !cart.customer_id
      : attaching
        ? !cart.customer_id || cart.customer_id === customerId
        : cart.customer_id === customerId);
    if (!allowed) {
      res.status(404).json({ message: "Bag not found" });
      return;
    }
    next();
  } catch {
    res.status(404).json({ message: "Bag not found" });
  }
}

export default defineMiddlewares({ routes: [{
  matcher: "/hooks/peach",
  methods: ["POST"],
  bodyParser: { preserveRawBody: true, sizeLimit: "64kb" },
}, {
  matcher: "/store/carts*",
  middlewares: [requireStorefrontBff],
}, {
  matcher: "/store/orders/:id/storefront-status",
  middlewares: [requireStorefrontBff],
}, {
  matcher: "/auth/customer/storefront-clerk",
  middlewares: [requireStorefrontBff],
}, {
  matcher: "/store/customers*",
  middlewares: [(req, res, next) => {
    res.setHeader("Cache-Control", "private, no-store, max-age=0");
    res.setHeader("X-Robots-Tag", "noindex, nofollow, noarchive");
    next();
  }],
}] });
