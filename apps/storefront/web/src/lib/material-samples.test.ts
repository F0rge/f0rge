import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { assert, describe, expect, it } from "vitest";
import { materialSample } from "./material-samples";

describe("photographic material samples", () => {
  it("requires the exact published SKU, axis and value", () => {
    expect(materialSample("P20307PC3", "Size", "Solo 111")).toBeUndefined();
    expect(materialSample("P20307PC3", "Upholstery material", "Solo 451")).toBeUndefined();
    expect(materialSample(null, "Upholstery material", "Solo 111")).toBeUndefined();
    expect(materialSample("__proto__", "Upholstery", "Solo 111")).toBeUndefined();
  });

  it("uses the original Swank photograph for the same Solo fabric on Kidman", () => {
    const kidman = materialSample("P20307PC3", "Upholstery material", "Solo 111");
    const swank = materialSample("P20305", "Upholstery", "Solo 111");
    assert.isDefined(kidman);
    expect(kidman).toEqual(swank);
    expect(kidman.sourceLabel).toContain("Swank");
    expect(kidman.swatch).not.toBe(kidman.detail);
    for (const url of [kidman.swatch, kidman.detail]) {
      expect(existsSync(fileURLToPath(new URL(`../../public${url}`, import.meta.url)))).toBe(true);
    }
  });

  it("preserves the native dimensions of smaller colour crops and the shared frame information", () => {
    const sample = materialSample("P62132X2", "Upholstery", "White PU / silver frame");
    expect(sample).toMatchObject({
      kind: "colour",
      label: "White PU",
      optionNote: "Silver frame on every colour.",
      width: 60,
      height: 66,
    });
    expect(sample?.detail).toBe(sample?.swatch);
  });
});
