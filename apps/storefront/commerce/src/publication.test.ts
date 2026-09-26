import { ProductStatus } from "@medusajs/framework/utils";
import { assertPublishedProductComplete, assertVariantsPurchasable, publicationProblems, type PublicationProduct, type PublicationVariant } from "./publication";
import type { MedusaContainer } from "@medusajs/framework/types";

const photos = ["https://images.example.com/sand-1.jpg", "https://images.example.com/sand-2.jpg", "https://images.example.com/sand-3.jpg"];
const product: PublicationProduct = {
  id: "prod_1", external_id: "firstout-group-1", title: "Arc sofa", status: ProductStatus.PUBLISHED,
  description: "A comfortable two seat sofa with deep cushions, a sturdy timber frame, and washable covers for everyday family use.",
  metadata: { dimension_unit: "cm", care_instructions: "Spot clean with a mild detergent and dry naturally." },
  options: [{ title: "Colour" }], images: photos.map((url) => ({ url })), sales_channels: [{ id: "sc_1" }],
};
const variant: PublicationVariant = {
  id: "variant_1", sku: "ARC-SAND", material: "Linen blend", length: 200, width: 90, height: 80,
  options: [{ option: { title: "Colour" }, value: "Sand" }],
  prices: [{ amount: 11500, currency_code: "zar" }],
  metadata: {
    source_sku_id: "e4653558-60c7-4be7-a416-76fc2c055b8f", source_price_includes_tax: true,
    source_available_quantity: 2, suitable_image_urls: photos,
  },
};

test("allows only a complete, published, channel-available variant", () => {
  expect(publicationProblems(product, variant, "sc_1")).toEqual([]);
  expect(publicationProblems(product, { ...variant, metadata: { ...variant.metadata, suitable_image_urls: JSON.stringify(photos) } }, "sc_1")).toEqual([]);
  expect(publicationProblems({ ...product, status: ProductStatus.DRAFT }, variant, "sc_1")).toContain("product is not published");
  expect(publicationProblems(product, variant, "sc_2")).toContain("product is not in the cart sales channel");
});

test("requires explicit suitable public images for the selected finish", () => {
  expect(publicationProblems(product, { ...variant, metadata: { ...variant.metadata, suitable_image_urls: photos.slice(0, 2) } })).toContain(
    "three public gallery photos attested for this variant are required",
  );
  expect(publicationProblems(product, { ...variant, metadata: { ...variant.metadata, suitable_image_urls: [...photos.slice(0, 2), "https://private.example.com/charcoal.jpg"] } })).toContain(
    "three public gallery photos attested for this variant are required",
  );
  expect(publicationProblems(product, { ...variant, metadata: { ...variant.metadata, suitable_image_urls: [...photos.slice(0, 2), "https://images.example.com/sand-3.jpg?token=secret"] } })).toContain(
    "three public gallery photos attested for this variant are required",
  );
  for (const host of ["127.0.0.1", "10.0.0.1", "192.168.1.2", "foo.internal", "localhost", "[::1]"]) {
    const urls = [1, 2, 3].map((index) => `https://${host}/sand-${index}.jpg`);
    const privateGallery = { ...product, images: urls.map((url) => ({ url })) };
    const privateVariant = { ...variant, metadata: { ...variant.metadata, suitable_image_urls: urls } };
    expect(publicationProblems(privateGallery, privateVariant)).toContain(
      "three public gallery photos attested for this variant are required",
    );
  }
});

test("accepts local generated demo photos only with the explicit non-production fixture flag", () => {
  const oldFlag = process.env.STOREFRONT_ALLOW_LOCAL_TEST_IMAGES;
  const oldNodeEnv = process.env.NODE_ENV;
  const localPhotos = [1, 2, 3].map((index) => `http://127.0.0.1:3004/demo/arc-${index}.jpg`);
  const localProduct = { ...product, images: localPhotos.map((url) => ({ url })) };
  const localVariant = { ...variant, metadata: { ...variant.metadata, suitable_image_urls: localPhotos } };
  try {
    process.env.STOREFRONT_ALLOW_LOCAL_TEST_IMAGES = "true";
    process.env.NODE_ENV = "development";
    expect(publicationProblems(localProduct, localVariant)).toEqual([]);
    process.env.NODE_ENV = "production";
    expect(publicationProblems(localProduct, localVariant)).toContain(
      "three public gallery photos attested for this variant are required",
    );
    process.env.NODE_ENV = "development";
    process.env.STOREFRONT_ALLOW_LOCAL_TEST_IMAGES = "false";
    expect(publicationProblems(localProduct, localVariant)).toContain(
      "three public gallery photos attested for this variant are required",
    );
  } finally {
    if (oldFlag === undefined) delete process.env.STOREFRONT_ALLOW_LOCAL_TEST_IMAGES;
    else process.env.STOREFRONT_ALLOW_LOCAL_TEST_IMAGES = oldFlag;
    if (oldNodeEnv === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = oldNodeEnv;
  }
});

test("requires tax-inclusive price, dimensions, care, and availability or lead time", () => {
  const noStock = { ...variant, metadata: { ...variant.metadata, source_available_quantity: 0 } };
  expect(publicationProblems(product, noStock)).toContain("stock or a positive lead time is required");
  expect(publicationProblems(product, { ...noStock, metadata: { ...noStock.metadata, lead_time_days: "21" } })).toEqual([]);
  expect(publicationProblems(product, { ...variant, metadata: { ...variant.metadata, source_price_includes_tax: false } })).toContain("tax-inclusive ZAR price is missing");
  expect(publicationProblems(product, { ...variant, width: null })).toContain("dimensions or dimension unit are missing");
  expect(publicationProblems({ ...product, metadata: {} }, variant)).toContain("material or care instructions are missing");
});

test("the Medusa query seam rejects a direct cart addition for an incomplete variant", async () => {
  const graph = jest.fn().mockResolvedValue({ data: [{ ...variant, product: { ...product, status: ProductStatus.DRAFT } }] });
  const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;
  await expect(assertVariantsPurchasable(container, [variant.id], "sc_1")).rejects.toThrow("not published");
  expect(graph).toHaveBeenCalledWith(expect.objectContaining({
    entity: "product_variant", filters: { id: [variant.id] },
  }));
});

test("rejects an incomplete Firstout product created directly as published", async () => {
  const graph = jest.fn().mockResolvedValue({
    data: [{ ...product, variants: [{ ...variant, length: null }] }],
  });
  const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;
  await expect(assertPublishedProductComplete(container, product.id)).rejects.toThrow("cannot be published");
});

test("cart completion rejects a variant that was removed from its sales channel", async () => {
  const graph = jest.fn().mockResolvedValue({ data: [{ ...variant, product }] });
  const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;
  await expect(assertVariantsPurchasable(container, [variant.id], "sc_removed")).rejects.toThrow("sales channel");
});
