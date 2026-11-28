import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { MedusaVariant, StoreProduct } from "@/lib/medusa";
import { publishedDimensions, unqualifiedLegacySize } from "@/lib/product-dimensions";
import { DimensionsFit } from "./dimensions-fit";

const product: StoreProduct = {
  id: "table", handle: "table", title: "Table", description: null, variants: [],
  metadata: { dimension_unit: "mm" }, length: 1000, width: 800, height: 700,
};
const variant: MedusaVariant = {
  id: "round", sku: "round",
  metadata: { dimensions_cm: { diameter: 150, height: 76, width: null, depth: null } },
};

function render(piece: StoreProduct, selected: MedusaVariant) {
  return renderToStaticMarkup(createElement(DimensionsFit, {
    title: piece.title, gallery: [], sku: selected.sku, measurements: publishedDimensions(piece, selected),
  }));
}

describe("product fit measurement fallbacks", () => {
  it("keeps a round variant's facts when its studio photo is unavailable", () => {
    const html = render(product, variant);
    expect(html).toContain("<dt>Diameter</dt><dd>150 cm</dd>");
    expect(html).toContain("<dt>Height</dt><dd>76 cm</dd>");
    expect(html).toContain("<dt>Circumference</dt><dd>≈ 471.2 cm</dd>");
    expect(html).not.toContain("<figure");
    expect(html).not.toContain("Width");
  });

  it("uses only positive measurements published for this variant", () => {
    const partial = { ...variant, metadata: { dimensions_cm: { diameter: 0, height: 72, width: Infinity, depth: -1 } } };
    expect(publishedDimensions(product, partial)).toEqual([{ axis: "height", value: 72, unit: "cm" }]);
    const empty = { ...variant, metadata: { dimensions_cm: { diameter: null, height: NaN, width: null, depth: null } } };
    expect(render(product, empty)).toBe("");
  });

  it("retains complete legacy dimensions with their original axis order and unit", () => {
    const legacy = { ...variant, metadata: null, width: 750 };
    const html = render(product, legacy);
    expect(html).toContain("<dt>Size (L × W × H)</dt><dd>1000 × 750 × 700 mm</dd>");
    expect(unqualifiedLegacySize(product, legacy)).toBeNull();
    const unknownUnit = { ...product, metadata: null };
    expect(render(unknownUnit, legacy)).toBe("");
    expect(unqualifiedLegacySize(unknownUnit, legacy)).toBe("1000 × 750 × 700");
    expect(unqualifiedLegacySize({ ...unknownUnit, length: null }, legacy)).toBeNull();
  });
});
