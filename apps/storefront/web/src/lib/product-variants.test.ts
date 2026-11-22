import { describe, expect, it } from "vitest";
import type { MedusaVariant, StoreProduct } from "./medusa";
import { pickVariant, productVariantOptions, selectedImages } from "./product-variants";

const variant = (
  id: string,
  colour: string,
  size: string,
  urls: string[] = [],
): MedusaVariant => ({
  id,
  sku: id,
  options: [
    { id: `colour-${id}`, option_id: "colour", value: colour },
    { id: `size-${id}`, option_id: "size", value: size },
  ],
  images: urls.map((url) => ({ id: url, url })),
});

const silver = variant("silver", "Silver", "80 cm", ["/s-front.jpg", "/s-side.jpg"]);
const goldSmall = variant("gold-small", "Gold", "60 cm", ["/g-side.jpg", "/g-front.jpg"]);
goldSmall.metadata = { suitable_image_urls: ["/g-front.jpg", "/g-side.jpg", "/missing.jpg"] };
const goldLarge = variant("gold-large", "Gold", "80 cm");
const product: StoreProduct = {
  id: "product",
  handle: "product",
  title: "Coffee table",
  description: null,
  options: [
    { id: "colour", title: "Colour", values: ["Silver", "Gold", "Bronze"].map((value) => ({ id: value, value })) },
    { id: "size", title: "Size", values: ["60 cm", "80 cm"].map((value) => ({ id: value, value })) },
  ],
  variants: [silver, goldSmall, goldLarge],
};

describe("approved product variants", () => {
  it("limits option values to available SKU combinations", () => {
    expect(productVariantOptions(product).map((option) => option.availableValues)).toEqual([
      ["Silver", "Gold"], ["60 cm", "80 cm"],
    ]);
    expect(pickVariant(product.variants, silver, "colour", "Gold")).toBe(goldLarge);
    expect(pickVariant(product.variants, silver, "size", "60 cm")).toBe(goldSmall);
    expect(pickVariant(product.variants, silver, "colour", "Bronze")).toBeUndefined();
  });

  it("uses ordered images for the chosen SKU regardless of relation order", () => {
    expect(selectedImages(product, goldSmall)).toEqual(["/g-front.jpg", "/g-side.jpg"]);
    expect(selectedImages(product, silver)).toEqual(["/s-front.jpg", "/s-side.jpg"]);
  });
});
