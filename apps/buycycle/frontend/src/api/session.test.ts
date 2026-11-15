import { expect, it } from "vitest";
import { IdentityChanged, IdentitySession } from "./session";
it("invalidates the whole identity epoch and refuses requests or replies after a switch", () => {
  const old = new IdentitySession("person-a");
  const pending = old.request();
  expect(pending.headers["X-Buycycle-Expected-Identity"]).toBe("person-a");
  old.invalidate();
  expect(pending.signal.aborted).toBe(true);
  expect(() => old.assertActive()).toThrow(IdentityChanged);
  expect(() => old.request()).toThrow(IdentityChanged);
  const next = new IdentitySession("person-a");
  expect(next.epoch).not.toBe(old.epoch);
  expect(next.active).toBe(true);
});
