import { describe, expect, it } from "vitest";
import { frontendHeaders, frontendHost, RESERVED_SLUGS } from "./tenant-host";

describe("tenant host forwarding", () => {
  it("accepts only exact named hosts and valid tenant slugs", () => {
    for (const host of [
      "firstout.co.za",
      "www.firstout.co.za",
      "app.firstout.co.za",
      "shop-2.app.firstout.co.za",
    ])
      expect(frontendHost(host)).toBe(host);
    for (const host of [
      "shop.app.firstout.co.za.attacker.com",
      "evilfirstout.co.za",
      "a.b.app.firstout.co.za",
      "-a.app.firstout.co.za",
      "a_.app.firstout.co.za",
      "firstout.co.za:444",
      "firstout.co.za.",
      "firstout.co.za,evil.com",
      " firstout.co.za",
      "https://firstout.co.za",
      ...[...RESERVED_SLUGS].map((s) => `${s}.app.firstout.co.za`),
    ])
      expect(frontendHost(host)).toBeNull();
  });
  it("allows loopback only with explicit local configuration", () => {
    expect(frontendHost("localhost:3003")).toBeNull();
    expect(frontendHost("localhost:3003", true)).toBe("localhost:3003");
    expect(frontendHost("localhost.evil.com", true)).toBeNull();
  });
  it("overwrites attacker-supplied forwarding headers from actual Host", () => {
    const headers = frontendHeaders(
      new Headers({
        host: "firstout.app.firstout.co.za",
        "x-firstout-frontend-host": "other.app.firstout.co.za",
        "x-forwarded-host": "other.app.firstout.co.za",
        forwarded: "host=other.app.firstout.co.za",
        "x-firstout-proxy-secret": "attacker",
      }),
      false,
      "synthetic-proxy",
    );
    expect(headers?.get("x-firstout-frontend-host")).toBe(
      "firstout.app.firstout.co.za",
    );
    expect(headers?.get("x-firstout-proxy-secret")).toBe("synthetic-proxy");
    expect(headers?.has("x-forwarded-host")).toBe(false);
    expect(headers?.has("forwarded")).toBe(false);
    expect(
      frontendHeaders(
        new Headers({
          host: "evil.com",
          "x-firstout-frontend-host": "firstout.co.za",
        }),
      ),
    ).toBeNull();
  });
});
