import { describe, expect, it } from "vitest";

import { checkSlug, passwordStrength, slugify } from "./slug";

describe("slugify", () => {
  it("derives a workspace slug from a legal name", () => {
    expect(slugify("Acme Holdings (Pty) Ltd")).toBe("acme-holdings");
    expect(slugify("Kramer & Sons")).toBe("kramer-and-sons");
    expect(slugify("  Émile   Décor ")).toBe("emile-decor");
  });

  it("caps length at 32 without a trailing dash", () => {
    const slug = slugify("a very long trading name for a distribution company in south africa");
    expect(slug.length).toBeLessThanOrEqual(32);
    expect(slug.endsWith("-")).toBe(false);
  });
});

describe("checkSlug", () => {
  it("accepts a normal slug", () => {
    expect(checkSlug("acme")).toEqual({ ok: true });
  });

  it("rejects reserved, short, and invalid slugs", () => {
    expect(checkSlug("vellano")).toEqual({ ok: false, reason: "reserved" });
    expect(checkSlug("ab")).toEqual({ ok: false, reason: "short" });
    expect(checkSlug("Acme Shop")).toEqual({ ok: false, reason: "invalid" });
    expect(checkSlug("-acme")).toEqual({ ok: false, reason: "invalid" });
  });
});

describe("passwordStrength", () => {
  it("scores longer, mixed passwords higher", () => {
    expect(passwordStrength("")).toBe(0);
    expect(passwordStrength("short")).toBe(0);
    expect(passwordStrength("twelvechars!")).toBeGreaterThanOrEqual(2);
    expect(passwordStrength("Correct Horse Battery 9")).toBe(4);
  });
});
