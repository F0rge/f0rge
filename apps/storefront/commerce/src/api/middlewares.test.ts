import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import storefrontMiddlewares, { requireStorefrontBff } from "./middlewares";

type FakeResponse = {
  statusCode?: number;
  headers: Record<string, string>;
  body?: unknown;
  setHeader(name: string, value: string): void;
  status(code: number): FakeResponse;
  json(value: unknown): FakeResponse;
};

function setup(path: string, owner: string | null, customerId?: string) {
  const graph = jest.fn(async () => ({ data: owner ? [{ id: "cart_test", customer_id: owner }] : [{ id: "cart_test", customer_id: null }] }));
  const req = {
    originalUrl: path,
    path,
    params: {},
    headers: {
      "x-storefront-bff-secret": "test-secret-that-is-long-enough-32-characters",
      ...(customerId ? { "x-storefront-customer-id": customerId } : {}),
    },
    scope: { resolve: jest.fn((key: string) => key === ContainerRegistrationKeys.QUERY ? { graph } : undefined) },
  } as unknown as MedusaRequest;
  const response: FakeResponse = {
    headers: {},
    setHeader(name, value) { this.headers[name] = value; return this; },
    status(code) { this.statusCode = code; return this; },
    json(value) { this.body = value; return this; },
  };
  const next = jest.fn();
  return { req, response: response as unknown as MedusaResponse, rawResponse: response, next, graph };
}

describe("storefront BFF cart ownership", () => {
  const previous = process.env.STOREFRONT_BFF_SECRET;
  beforeAll(() => { process.env.STOREFRONT_BFF_SECRET = "test-secret-that-is-long-enough-32-characters"; });
  afterAll(() => {
    if (previous === undefined) delete process.env.STOREFRONT_BFF_SECRET;
    else process.env.STOREFRONT_BFF_SECRET = previous;
  });

  it("registers the BFF guard on a broad Medusa wildcard before native API routes", () => {
    const routes = storefrontMiddlewares.routes ?? [];
    expect(routes.find((route) => route.matcher === "/*")?.middlewares).toContain(requireStorefrontBff);
  });

  it("allows an anonymous browser to use an ownerless guest cart", async () => {
    const call = setup("/store/carts/cart_test/line-items", null);
    await requireStorefrontBff(call.req, call.response, call.next);
    expect(call.next).toHaveBeenCalledTimes(1);
    expect(call.rawResponse.headers["Cache-Control"]).toContain("no-store");
  });

  it("allows only the linked customer to read a customer-owned cart", async () => {
    const owner = setup("/store/carts/cart_test", "cus_owner", "cus_owner");
    await requireStorefrontBff(owner.req, owner.response, owner.next);
    expect(owner.next).toHaveBeenCalledTimes(1);

    const other = setup("/store/carts/cart_test", "cus_owner", "cus_other");
    await requireStorefrontBff(other.req, other.response, other.next);
    expect(other.next).not.toHaveBeenCalled();
    expect(other.rawResponse.statusCode).toBe(404);
  });

  it("denies a logged-out replay of a customer-owned cart capability", async () => {
    const call = setup("/store/carts/cart_test", "cus_owner");
    await requireStorefrontBff(call.req, call.response, call.next);
    expect(call.next).not.toHaveBeenCalled();
    expect(call.rawResponse.statusCode).toBe(404);
  });

  it("allows attaching an unowned guest cart, but never transferring an owned cart", async () => {
    const guest = setup("/store/carts/cart_test/storefront-customer", null, "cus_new");
    await requireStorefrontBff(guest.req, guest.response, guest.next);
    expect(guest.next).toHaveBeenCalledTimes(1);

    const transfer = setup("/store/carts/cart_test/storefront-customer", "cus_owner", "cus_other");
    await requireStorefrontBff(transfer.req, transfer.response, transfer.next);
    expect(transfer.next).not.toHaveBeenCalled();
    expect(transfer.rawResponse.statusCode).toBe(404);
  });

  it("does not interpret order IDs as cart IDs on private order-status routes", async () => {
    const call = setup("/store/orders/order_test/storefront-status", null);
    await requireStorefrontBff(call.req, call.response, call.next);
    expect(call.next).toHaveBeenCalledTimes(1);
    expect(call.graph).not.toHaveBeenCalled();
  });

  it("protects order and customer native APIs even when their paths are encoded", async () => {
    for (const path of [
      "/store/orders",
      "/store/orders%2forder_test",
      "/store/%256Frders/order_test",
      "/store/customers/me",
      "/STORE/orders/order_test",
      "/STORE/customers/me",
      "/store/carts%2fcart_test",
      "/store/storefront-alerts/test",
      "/auth/customer/storefront-clerk",
      "/auth/customer/storefront%2Dclerk/register",
    ]) {
      const call = setup(path, null);
      call.req.headers["x-storefront-bff-secret"] = "wrong";
      await requireStorefrontBff(call.req, call.response, call.next);
      expect(call.next).not.toHaveBeenCalled();
      expect(call.rawResponse.statusCode).toBe(403);
    }
  });

  it("requires the BFF secret and rejects native order transfer routes", async () => {
    const transfer = setup("/store/orders/order_test/transfer/request", null);
    await requireStorefrontBff(transfer.req, transfer.response, transfer.next);
    expect(transfer.rawResponse.statusCode).toBe(404);
    expect(transfer.next).not.toHaveBeenCalled();

    const encodedTransfer = setup("/store/orders/order_test/%74ransfer/request", null);
    await requireStorefrontBff(encodedTransfer.req, encodedTransfer.response, encodedTransfer.next);
    expect(encodedTransfer.rawResponse.statusCode).toBe(404);
    expect(encodedTransfer.next).not.toHaveBeenCalled();

    const direct = setup("/store/orders/order_test", null);
    delete direct.req.headers["x-storefront-bff-secret"];
    await requireStorefrontBff(direct.req, direct.response, direct.next);
    expect(direct.rawResponse.statusCode).toBe(403);
    expect(direct.next).not.toHaveBeenCalled();
  });
});

describe("Peach webhook route hardening", () => {
  it("blocks plain and encoded native Peach POSTs but passes other providers", async () => {
    const routes = storefrontMiddlewares.routes ?? [];
    const nativeRoute = routes.find((route) => route.matcher === "/hooks/payment/*");
    expect(nativeRoute?.methods).toEqual(["POST"]);
    expect(nativeRoute?.middlewares).toHaveLength(1);
    const handler = nativeRoute?.middlewares?.[0];
    if (!handler) throw new Error("Native Peach webhook blocker is not registered");

    for (const path of ["/hooks/payment/peach_sandbox", "/hooks/payment/peach%5Fsandbox", "/hooks/payment/Peach_Sandbox"]) {
      const call = setup(path, null);
      await handler(call.req, call.response, call.next);
      expect(call.rawResponse.statusCode).toBe(404);
      expect(call.next).not.toHaveBeenCalled();
    }

    const otherProvider = setup("/hooks/payment/other_provider", null);
    await handler(otherProvider.req, otherProvider.response, otherProvider.next);
    expect(otherProvider.next).toHaveBeenCalledTimes(1);
    expect(otherProvider.rawResponse.statusCode).toBeUndefined();

    const malformed = setup("/hooks/payment/peach%5sandbox", null);
    await handler(malformed.req, malformed.response, malformed.next);
    expect(malformed.rawResponse.statusCode).toBe(404);
    expect(malformed.next).not.toHaveBeenCalled();

    const customRoute = routes.find((route) => route.matcher === "/hooks/peach");
    expect(customRoute?.methods).toEqual(["POST"]);
    expect(customRoute?.bodyParser).toMatchObject({ preserveRawBody: true, sizeLimit: "64kb" });
    expect(customRoute?.middlewares).not.toContain(handler);
  });
});
