import { describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

vi.mock("@/lib/bag-server", () => ({
  cartCookie: "collector_cart",
  emailOrderAccessCookie: "collector_email_order_access",
  orderAccessCookie: "collector_order_access",
}));

import { POST } from "./route";

describe("customer logout BFF", () => {
  it("expires all protected browser capabilities on explicit logout", async () => {
    const request = new NextRequest("https://store.example/api/account/logout", {
      method: "POST", headers: { host: "store.example", origin: "https://store.example" },
    });
    const response = await POST(request);
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("private, no-store, max-age=0");
    const cleared = response.cookies.getAll().map((cookie) => cookie.name).sort();
    expect(cleared).toEqual(["collector_cart", "collector_email_order_access", "collector_order_access"].sort());
    expect(response.cookies.get("collector_email_order_access")?.path).toBe("/api/order/confirmation");
    expect(response.headers.get("set-cookie")).not.toContain("medusa");
  });
});
