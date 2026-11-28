import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { MedusaVariant, StoreProduct } from "@/lib/medusa";
import { VariantSelector } from "./variant-selector";

function piece(axes: string[], rows: [string, string[], string?][]): StoreProduct {
  const variants: MedusaVariant[] = rows.map(([sku, values, hex]) => ({
    id: sku, sku, options: values.map((value, index) => ({ id: value, option_id: axes[index], value })),
    metadata: { swatch_hex: hex },
  }));
  return { id: "piece", handle: "piece", title: "Piece", description: null, options: axes.map((title) => ({ id: title, title })), variants };
}

function render(product: StoreProduct) {
  return renderToStaticMarkup(createElement(VariantSelector, { product, active: product.variants[0], onSelect: () => {} }));
}

describe("storefront variant presentation", () => {
  it("adds only verified samples while keeping a newly published upholstery option selectable", () => {
    const html = render(piece(["Upholstery material"], [
      ["P20307PC3", ["Solo 111"]], ["P20302PC3", ["Taupe Fabric"]], ["NEW", ["New upholstery"]],
    ]));
    expect(html).toContain("See fabric close-up");
    expect(html).toContain('aria-label="Sand Fabric"');
    expect(html).toContain('aria-label="Taupe Fabric"');
    expect(html).toContain('aria-label="New upholstery"');
    expect(html.match(/<img /g)).toHaveLength(2);
    expect(html).toContain('aria-expanded="false"');
  });

  it("keeps frame details in the labels if a new chair finish makes the shared note inapplicable", () => {
    const html = render(piece(["Upholstery"], [
      ["P62131X2", ["Grey / silver frame"]], ["P62132X2", ["White Faux Leather"]],
      ["NEW", ["Grey / wood frame"]],
    ]));
    expect(html).toContain('aria-label="Light Grey · Silver frame"');
    expect(html).toContain('aria-label="White Faux Leather · Silver frame"');
    expect(html).toContain('aria-label="Grey / wood frame"');
    expect(html).not.toContain(">Silver frame<");
  });

  it("shows the common silver frame once for all reviewed Alexa colours", () => {
    const html = render(piece(["Upholstery"], [
      ["P62131X2", ["Light Grey"]], ["P62132X2", ["White Faux Leather"]], ["P62129X2", ["Navy Velvet"]],
    ]));
    expect(html).toContain('aria-label="Navy Velvet"');
    expect(html.match(/>Silver frame</g)).toHaveLength(1);
  });

  it("uses an explicit SKU colour only for the colour axis of a multi-option piece", () => {
    const html = render(piece(["Colour", "Size"], [
      ["silver", ["Silver", "200 cm"], "#c0c0c0"], ["gold", ["Gold", "160 cm"], "#b8902e"],
    ]));
    expect(html.match(/type="radio"/g)).toHaveLength(2);
    expect(html).toContain('style="background-color:#c0c0c0"');
    expect(html).toContain('aria-pressed="true"');
    expect(html).toContain("160 cm");
    expect(html).not.toContain("Compare colours");
  });

  it("does not ascribe one SKU colour to two different finish axes or the same SKU's renamed option", () => {
    const ambiguous = render(piece(["Frame finish", "Upholstery colour"], [
      ["silver", ["Silver", "Navy"], "#c0c0c0"], ["gold", ["Gold", "Grey"], "#b8902e"],
    ]));
    expect(ambiguous).not.toContain('type="radio"');
    expect(ambiguous).toContain("Navy");
    const changed = render(piece(["Upholstery material"], [
      ["P20307PC3", ["New material"]], ["P20302PC3", ["Another new material"]],
    ]));
    expect(changed).not.toContain("<img");
    expect(changed).toContain("Another new material");
  });
});
