import { timingSafeEqual } from "node:crypto";
import { authenticate, defineMiddlewares, type MedusaNextFunction, type MedusaRequest, type MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import { verifiedStorefrontCustomer } from "../storefront-order-claims";

function normalizedPath(req: MedusaRequest): string | null {
  let path = (req.originalUrl || req.path || "").split("?", 1)[0];
  try {
    // Express can retain encoded separators in originalUrl. Decode repeatedly
    // so encoded or double-encoded protected prefixes cannot miss the guard.
    for (let pass = 0; pass < 8; pass += 1) {
      const decoded = decodeURIComponent(path);
      if (decoded === path) return path;
      path = decoded;
    }
    return /%(?:2f|2e|25)/i.test(path) ? null : path;
  } catch {
    return null;
  }
}

function denied(res: MedusaResponse, status = 403): void {
  res.status(status).json({ message: "Storefront access is restricted" });
}

async function checkCartOwner(req: MedusaRequest, res: MedusaResponse, next: MedusaNextFunction, path: string): Promise<void> {
  const cartMatch = /(?:^|\/)store\/carts\/(cart_[^/]+)(?:\/|$)/i.exec(path);
  if (!cartMatch || path.toLowerCase().endsWith("/storefront-confirmation")) {
    next();
    return;
  }

  const customerId = req.headers["x-storefront-customer-id"];
  const attaching = path.toLowerCase().endsWith("/storefront-customer");
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

async function checkNativeOrderDetail(req: MedusaRequest, res: MedusaResponse, next: MedusaNextFunction, path: string): Promise<void> {
  const segments = path.split("/").filter(Boolean);
  const orderId = segments[2];
  if (segments.length !== 3 || !orderId || !/^order_[A-Za-z0-9_-]+$/.test(orderId)) {
    res.status(404).json({ message: "Order not found" });
    return;
  }
  const authenticateCustomer = authenticate("customer", ["session", "bearer"]);
  authenticateCustomer(req, res, async (error?: unknown) => {
    if (error) {
      next(error as Error);
      return;
    }
    const actor = (req as MedusaRequest & { auth_context?: { actor_type?: unknown; actor_id?: unknown } }).auth_context;
    if (actor?.actor_type !== "customer" || typeof actor.actor_id !== "string" || !/^cus_[A-Za-z0-9_-]+$/.test(actor.actor_id)) {
      denied(res, 404);
      return;
    }
    try {
      const query = req.scope.resolve(ContainerRegistrationKeys.QUERY);
      const { data } = await query.graph({
        entity: "order",
        fields: ["id", "customer_id"],
        filters: { id: orderId, customer_id: actor.actor_id },
      });
      if (!data.length) {
        res.status(404).json({ message: "Order not found" });
        return;
      }
      next();
    } catch {
      res.status(404).json({ message: "Order not found" });
    }
  });
}

async function guardStorefrontCustomerRoutes(req: MedusaRequest, res: MedusaResponse, next: MedusaNextFunction, path: string): Promise<void> {
  const lowerPath = path.toLowerCase();
  const segments = lowerPath.split("/").filter(Boolean);
  if (segments[1] === "orders") {
    if (segments.some((segment) => segment === "transfer" || segment === "transfers")) {
      res.status(404).json({ message: "Order transfer is unavailable" });
      return;
    }
    if (segments[2] === "storefront-account") {
      const authenticateCustomer = authenticate("customer", ["session", "bearer"]);
      authenticateCustomer(req, res, (error?: unknown) => {
        if (error) {
          next(error as Error);
          return;
        }
        if (!verifiedStorefrontCustomer((req as MedusaRequest & { auth_context?: unknown }).auth_context)) {
          denied(res, 401);
          return;
        }
        next();
      });
      return;
    }
    if (segments[2] === "storefront-status" || segments[3] === "storefront-status") {
      // Confirmation/status access has its separate order-bound capability.
      next();
      return;
    }
    if (segments.length === 2 && req.method === "GET") {
      // Medusa's native list endpoint already requires a customer actor and
      // applies that actor as customer_id. The BFF secret is checked above.
      next();
      return;
    }
    if (segments.length === 3 && req.method === "GET") {
      await checkNativeOrderDetail(req, res, next, path);
      return;
    }
    if (segments.length === 2 || segments[2]?.startsWith("order_")) {
      res.status(404).json({ message: "Order route is unavailable" });
      return;
    }
  }
  next();
}

export async function requireStorefrontBff(req: MedusaRequest, res: MedusaResponse, next: MedusaNextFunction): Promise<void> {
  const path = normalizedPath(req);
  if (!path) {
    denied(res, 404);
    return;
  }
  const lowerPath = path.toLowerCase();
  const protectedStoreRoute = /^\/store\/(?:carts|orders|customers)(?:\/|$)/i.test(path) ||
    /^\/auth\/customer\/storefront-clerk(?:\/|$)/i.test(path);
  if (!protectedStoreRoute) {
    next();
    return;
  }

  const secret = process.env.STOREFRONT_BFF_SECRET;
  const supplied = req.headers["x-storefront-bff-secret"];
  if (!secret || secret.length < 32 || typeof supplied !== "string") {
    denied(res);
    return;
  }
  const expected = Buffer.from(secret);
  const received = Buffer.from(supplied);
  if (expected.length !== received.length || !timingSafeEqual(expected, received)) {
    denied(res);
    return;
  }
  res.setHeader("Cache-Control", "private, no-store, max-age=0");
  res.setHeader("X-Robots-Tag", "noindex, nofollow, noarchive");

  if (lowerPath.startsWith("/store/carts/")) {
    await checkCartOwner(req, res, next, path);
    return;
  }
  await guardStorefrontCustomerRoutes(req, res, next, path);
}

export function blockNativePeachWebhook(req: MedusaRequest, res: MedusaResponse, next: MedusaNextFunction): void {
  const path = normalizedPath(req);
  const providerSegment = path?.split("/")[3];
  if (!providerSegment || providerSegment.toLowerCase() === "peach_sandbox") {
    res.status(404).json({ message: "Not found" });
    return;
  }
  next();
}

export default defineMiddlewares({ routes: [{
  matcher: "/hooks/peach",
  methods: ["POST"],
  bodyParser: { preserveRawBody: true, sizeLimit: "64kb" },
}, {
  matcher: "/hooks/payment/*",
  methods: ["POST"],
  middlewares: [blockNativePeachWebhook],
}, {
  // The normalizer cheaply passes unrelated paths. A broad string wildcard
  // catches case-insensitive and encoded Store/Auth prefixes before native
  // routes; regex matchers are not reliable for mounted Express middleware.
  matcher: "/*",
  middlewares: [requireStorefrontBff],
}, {
  matcher: "/store/*",
  middlewares: [(req, res, next) => {
    const path = normalizedPath(req);
    if (path && /^\/store\/(?:carts|orders|customers)(?:\/|$)/i.test(path)) {
      res.setHeader("Cache-Control", "private, no-store, max-age=0");
      res.setHeader("X-Robots-Tag", "noindex, nofollow, noarchive");
    }
    next();
  }],
}] });
