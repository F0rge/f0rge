import { describe, expect, it } from "vitest";

import { tenantHostFromHostname, tenantHostFromRequest } from "./tenant";

describe("tenant host helpers", () => {
  it("strips port and lowercases", () => {
    expect(tenantHostFromHostname("Acme.Localhost:3003")).toBe("acme.localhost");
    expect(tenantHostFromHostname("localhost.")).toBe("localhost");
  });

  it("prefers X-Tenant-Host on proxied requests", () => {
    const request = new Request("http://localhost:3003/api/v1/nia/threads/t1/run", {
      headers: {
        host: "localhost:3003",
        "x-tenant-host": "acme.localhost:443",
      },
    });
    expect(tenantHostFromRequest(request)).toBe("acme.localhost");
  });

  it("falls back to Host without port", () => {
    const request = new Request("http://acme.localhost:3003/api/v1/nia/threads/t1/run", {
      headers: { host: "acme.localhost:3003" },
    });
    expect(tenantHostFromRequest(request)).toBe("acme.localhost");
  });

  it("falls back to the request URL hostname when Host is absent", () => {
    const request = new Request("http://acme.localhost:3003/api/v1/nia/threads/t1/run");
    expect(tenantHostFromRequest(request)).toBe("acme.localhost");
  });
});
