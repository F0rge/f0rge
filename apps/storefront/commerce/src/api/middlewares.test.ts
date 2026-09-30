import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import { requireStorefrontBff } from "./middlewares";

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
});
