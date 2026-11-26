import { ProductStatus } from "@medusajs/framework/utils";
import { assertPublishedProductComplete, assertVariantsPurchasable, basketVariantTotals, CURATED_PRODUCT_METADATA_KEY, publicationProblems, type PublicationProduct, type PublicationVariant } from "./publication";
import type { MedusaContainer } from "@medusajs/framework/types";
import { publicFileBackendUrl } from "./file-storage-url";

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

test("allows a catalogue product without photos and rejects an attested photo that is not public", () => {
  const withoutPhotos = { ...(variant.metadata || {}) };
  delete withoutPhotos.suitable_image_urls;
  expect(publicationProblems(
    { ...product, description: null, metadata: {}, images: [] },
    { ...variant, material: null, length: null, width: null, height: null, images: [], metadata: withoutPhotos },
    "sc_1",
  )).toEqual([]);
  expect(publicationProblems(product, { ...variant, metadata: { ...variant.metadata, suitable_image_urls: photos.slice(0, 2) } })).toEqual([]);
  expect(publicationProblems(product, { ...variant, metadata: { ...variant.metadata, suitable_image_urls: ["https://images.example.com/not-in-the-gallery.jpg"] } })).toContain(
    "attested gallery photos must be public images on this variant",
  );
  expect(publicationProblems(product, { ...variant, metadata: { ...variant.metadata, suitable_image_urls: [...photos.slice(0, 2), "https://private.example.com/charcoal.jpg"] } })).toContain(
    "attested gallery photos must be public images on this variant",
  );
  expect(publicationProblems(product, { ...variant, metadata: { ...variant.metadata, suitable_image_urls: [...photos.slice(0, 2), "https://images.example.com/sand-3.jpg?token=secret"] } })).toContain(
    "attested gallery photos must be public images on this variant",
  );
  for (const host of ["127.0.0.1", "10.0.0.1", "192.168.1.2", "foo.internal", "localhost", "[::1]"]) {
    const urls = [1, 2, 3].map((index) => `https://${host}/sand-${index}.jpg`);
    const privateGallery = { ...product, images: urls.map((url) => ({ url })) };
    const privateVariant = { ...variant, metadata: { ...variant.metadata, suitable_image_urls: urls } };
    expect(publicationProblems(privateGallery, privateVariant)).toContain(
      "attested gallery photos must be public images on this variant",
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
      "attested gallery photos must be public images on this variant",
    );
    process.env.NODE_ENV = "development";
    process.env.STOREFRONT_ALLOW_LOCAL_TEST_IMAGES = "false";
    expect(publicationProblems(localProduct, localVariant)).toContain(
      "attested gallery photos must be public images on this variant",
    );
  } finally {
    if (oldFlag === undefined) delete process.env.STOREFRONT_ALLOW_LOCAL_TEST_IMAGES;
    else process.env.STOREFRONT_ALLOW_LOCAL_TEST_IMAGES = oldFlag;
    if (oldNodeEnv === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = oldNodeEnv;
  }
});

test("requires a tax-inclusive price and stock or a finite made-to-order offer", () => {
  const noStock = { ...variant, metadata: { ...variant.metadata, source_available_quantity: 0 } };
  expect(publicationProblems(product, noStock)).toContain("stock or a positive lead time is required");
  expect(publicationProblems(product, { ...noStock, metadata: { ...noStock.metadata, lead_time_days: "21" } })).toContain("stock or a positive lead time is required");
  expect(publicationProblems(product, { ...noStock, metadata: { ...noStock.metadata,
    storefront_made_to_order_offer: {
      id: "offer-1", remaining_capacity: 2, min_lead_time_days: 21, max_lead_time_days: 28,
      expires_at: new Date(Date.now() + 86_400_000).toISOString(),
    },
  } })).toEqual([]);
  expect(publicationProblems(product, { ...variant, metadata: { ...variant.metadata, source_price_includes_tax: false } })).toContain("tax-inclusive ZAR price is missing");
  expect(publicationProblems(product, { ...variant, width: null, material: null })).toEqual([]);
  expect(publicationProblems({ ...product, description: "Short oak tray.", metadata: {}, images: photos.map((url) => ({ url })) }, variant)).toEqual([]);
});

test("the Medusa query seam rejects a direct cart addition for an incomplete variant", async () => {
  const graph = jest.fn().mockResolvedValue({ data: [{ ...variant, product: { ...product, status: ProductStatus.DRAFT } }] });
  const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;
  await expect(assertVariantsPurchasable(container, [variant.id], "sc_1")).rejects.toThrow("not published");
  expect(graph).toHaveBeenCalledWith(expect.objectContaining({
    entity: "product_variant", filters: { id: [variant.id] },
  }));
});

test("rejects a published Firstout product with no price and no stock", async () => {
  const graph = jest.fn().mockResolvedValue({
    data: [{ ...product, variants: [{ ...variant, prices: [], metadata: { ...variant.metadata, source_price_includes_tax: false, source_available_quantity: 0 } }] }],
  });
  const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;
  await expect(assertPublishedProductComplete(container, product.id)).rejects.toThrow("cannot be published");
});

test("cart completion rejects a variant that was removed from its sales channel", async () => {
  const graph = jest.fn().mockResolvedValue({ data: [{ ...variant, product }] });
  const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;
  await expect(assertVariantsPurchasable(container, [variant.id], "sc_removed")).rejects.toThrow("sales channel");
  graph.mockResolvedValueOnce({ data: [{ ...variant, product: { ...product, external_id: "staff" } }] });
  await expect(assertVariantsPurchasable(container, [variant.id], "sc_removed")).rejects.toThrow("no longer available");
});

test("a curated product can show a sold-out option beside a stocked variant, but the bag still rejects it", async () => {
  const soldOut = { ...variant, id: "variant_2", metadata: { ...variant.metadata, source_available_quantity: 0 } };
  const curated = { ...product, metadata: { ...product.metadata, [CURATED_PRODUCT_METADATA_KEY]: true } };
  const graph = jest.fn()
    .mockResolvedValueOnce({ data: [{ ...curated, variants: [variant, soldOut] }] })
    .mockResolvedValueOnce({ data: [{ ...soldOut, product: curated }] });
  const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;
  await expect(assertPublishedProductComplete(container, product.id)).resolves.toBeUndefined();
  await expect(assertVariantsPurchasable(container, [soldOut.id], "sc_1")).rejects.toThrow("stock or a positive lead time is required");
});

test("cart writes count existing and incoming units together without disclosing the stock ceiling", async () => {
  const affected = new Set([variant.id]);
  const current = [{ variant_id: variant.id, quantity: 104 }];
  const total = (quantity: number) => basketVariantTotals([...current, { variant_id: variant.id, quantity }], affected);
  const graph = jest.fn().mockResolvedValue({ data: [{
    ...variant,
    product,
    metadata: { ...variant.metadata, source_available_quantity: 111, source_projected_quantity: 110 },
  }] });
  const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;
  await expect(assertVariantsPurchasable(container, [variant.id], "sc_1", total(6))).resolves.toBeUndefined();
  await expect(assertVariantsPurchasable(container, [variant.id], "sc_1", total(7)))
    .rejects.toThrow("That quantity is no longer available for this piece.");
});

test("a Firstout photo the sync stores on the hosted volume passes the public-image check", () => {
  const url = `${publicFileBackendUrl({ RAILWAY_PUBLIC_DOMAIN: "storefront-commerce-production.up.railway.app" })}/1763700000000-firstout-${variant.metadata?.source_sku_id}.jpg`;
  expect(publicationProblems(
    { ...product, images: [{ url }] },
    { ...variant, images: [{ url }], metadata: { ...variant.metadata, suitable_image_urls: [url] } },
    "sc_1",
  )).toEqual([]);
});

describe("selling rules on cart writes", () => {
  const rewriteWords = /\b(?:stock|inventory|remaining capacity)\b/i;
  const seam = (metadata: Record<string, unknown>, external_id = product.external_id) => {
    const graph = jest.fn().mockResolvedValue({ data: [{ ...variant, product: { ...product, external_id }, metadata: { ...variant.metadata, ...metadata } }] });
    const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;
    return (...quantities: number[]) => assertVariantsPurchasable(container, [variant.id], "sc_1",
      basketVariantTotals(quantities.map((quantity) => ({ variant_id: variant.id, quantity })), new Set([variant.id])));
  };
  const refusal = async (attempt: Promise<void>) => {
    const error = await attempt.then(() => null, (caught: Error) => caught);
    expect(error).not.toBeNull();
    expect(error!.message).not.toMatch(rewriteWords);
    return error!.message;
  };

  test("a total must be a multiple of the sell multiple and at least the minimum, across lines", async () => {
    const add = seam({ source_available_quantity: 10, sell_multiple: 2, min_quantity: 4 });
    expect(await refusal(add(3))).toBe("This piece is sold in sets of 2.");
    expect(await refusal(add(2))).toBe("The minimum order for this piece is 4.");
    expect(await refusal(add(2, 3))).toBe("This piece is sold in sets of 2.");
    await expect(add(4)).resolves.toBeUndefined();
    await expect(add(3, 1)).resolves.toBeUndefined();
    await expect(add(2, 2, 2)).resolves.toBeUndefined();
  });

  test("the cap is rounded down to the multiple, and a cap below the minimum refuses plainly", async () => {
    const oddCap = seam({ source_available_quantity: 5, sell_multiple: 2 });
    await expect(oddCap(4)).resolves.toBeUndefined();
    await expect(oddCap(6)).rejects.toThrow("That quantity is no longer available for this piece.");
    expect(await refusal(oddCap(5))).toBe("This piece is sold in sets of 2.");

    const short = seam({ source_available_quantity: 3, sell_multiple: 2, min_quantity: 4 });
    expect(await refusal(short(4))).toBe("The minimum order for this piece is 4, and fewer than 4 are available right now.");
    const single = seam({ source_available_quantity: 1, sell_multiple: 2 });
    expect(await refusal(single(2))).toBe("This piece is sold in sets of 2, and fewer than 2 are available right now.");
  });

  test("a variant without rules, a malformed rule and a non-Firstout product behave as before", async () => {
    await expect(seam({ source_available_quantity: 3 })(1)).resolves.toBeUndefined();
    await expect(seam({ source_available_quantity: 3, sell_multiple: null, min_quantity: "4" })(3)).resolves.toBeUndefined();
    await expect(seam({ sell_multiple: 2, min_quantity: 4 }, "staff-product")(1)).resolves.toBeUndefined();
  });

  test("cart completion does not check the rules: it runs after payment", async () => {
    const graph = jest.fn().mockResolvedValue({ data: [{ ...variant, product, metadata: { ...variant.metadata, sell_multiple: 2 } }] });
    const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;
    await expect(assertVariantsPurchasable(container, [variant.id], "sc_1")).resolves.toBeUndefined();
  });
});
