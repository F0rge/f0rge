import { describe, expect, it } from "vitest";
import type { MedusaVariant, StoreProduct } from "./medusa";
import { productMetaDescription, productStructuredData } from "./product-seo";

const production = {
  NEXT_PUBLIC_BASE_URL: "https://www.daskasas.co.za",
  RAILWAY_ENVIRONMENT_NAME: "production",
  STOREFRONT_INDEXING_ENABLED: "true",
  STOREFRONT_PRIVATE_PREVIEW: "off",
};
const path = "/product/11111111-1111-4111-8111-111111111111";
const canonical = production.NEXT_PUBLIC_BASE_URL + path;
const photo = "https://medusa.firstout.co.za/static/test-sofa.jpg";

const variant: MedusaVariant = {
  id: "variant_sofa",
  sku: "SOFA-1",
  material: "Oak",
  inventory_quantity: 3,
  calculated_price: { calculated_amount: 34999.95, currency_code: "zar" },
};
const product: StoreProduct = {
  id: "prod_sofa",
  title: "Fixture Sofa",
  handle: "firstout-11111111-1111-4111-8111-111111111111",
  description: null,
  status: "published",
  categories: [{ id: "sofas", name: "Sofas & Armchairs", handle: "sofas-armchairs" }],
  variants: [variant],
  images: [{ id: "photo", url: photo }],
};

function schema(piece: StoreProduct = product) {
  return JSON.parse(productStructuredData(piece, path, production) ?? "null");
}

describe("product search descriptions", () => {
  it("gives products with otherwise identical titles distinct descriptions based on public SKU facts", () => {
    expect(productMetaDescription(product)).toBe(
      "Explore Fixture Sofa at DasKasas. Collection: Sofas & Armchairs · Material: Oak · SKU: SOFA-1.",
    );
    expect(productMetaDescription({ ...product, variants: [{ ...variant, sku: "SOFA-2" }] })).toContain("SKU: SOFA-2");
  });

  it("prefers a meaningful description while stripping HTML and clipping long copy at a word boundary", () => {
    const override = "<p>Fixture Sofa suits compact living rooms.</p><script>private</script>";
    expect(productMetaDescription({ ...product, metadata: { seo_description: override } }))
      .toBe("Fixture Sofa suits compact living rooms.");
    const long = productMetaDescription({ ...product, description: "Oak with rounded edges. ".repeat(20) });
    expect(long).toMatch(/^Fixture Sofa\. Oak.+…$/);
    expect(long?.length).toBeLessThanOrEqual(170);
  });

  it("keeps concise editorial copy and skips an override that only repeats the title", () => {
    expect(productMetaDescription({ ...product, metadata: { seo_description: "Hand-finished oak." } }))
      .toBe("Fixture Sofa. Hand-finished oak.");
    expect(productMetaDescription({ ...product, description: "Linen upholstery", metadata: { seo_description: "Fixture Sofa." } }))
      .toBe("Fixture Sofa. Linen upholstery.");
  });
});

describe("product structured data", () => {
  it("serializes one canonical product with attached photos and its real rand price and stock", () => {
    const markup = productStructuredData({ ...product, title: "Fixture < Sofa" }, path, production);
    expect(markup).not.toContain("<");
    expect(schema()).toEqual({
      "@context": "https://schema.org",
      "@type": "Product",
      "@id": canonical + "#product",
      name: "Fixture Sofa",
      url: canonical,
      sku: "SOFA-1",
      material: "Oak",
      image: [photo],
      offers: {
        "@type": "Offer",
        price: 34999.95,
        priceCurrency: "ZAR",
        availability: "https://schema.org/InStock",
        url: canonical,
      },
    });
  });

  it("describes grouped variant choices and their deep links, selected images, and individual stock", () => {
    const photo2 = "/catalogue/fabric-sofa.jpg";
    const navy = { ...variant, options: [{ id: "navy", option_id: "colour", value: "Navy" }], images: product.images };
    const grey = {
      ...variant, id: "grey_cushion", sku: "SOFA-2", inventory_quantity: 0,
      options: [{ id: "grey", option_id: "colour", value: "Grey" }],
      images: [{ id: "grey", url: photo2 }],
    };
    const group = schema({
      ...product, options: [{ id: "colour", title: "Upholstery colour" }], variants: [navy, grey],
    });
    const greyUrl = canonical + "?variant=grey_cushion";
    expect(group).toMatchObject({
      "@type": "ProductGroup", url: canonical, productGroupID: product.id,
      variesBy: ["https://schema.org/color"],
      hasVariant: [
        { "@type": "Product", name: "Fixture Sofa – Navy", color: "Navy", image: [photo], url: canonical + "?variant=variant_sofa" },
        { "@type": "Product", name: "Fixture Sofa – Grey", color: "Grey", image: [production.NEXT_PUBLIC_BASE_URL + photo2], url: greyUrl,
          offers: { availability: "https://schema.org/OutOfStock", url: greyUrl } },
      ],
    });
  });

  it("preserves upholstery choices as named properties without treating a fabric code as a colour", () => {
    const first = { ...variant, options: [{ id: "fabric1", option_id: "fabric", value: "AS1687-9" }] };
    const second = {
      ...variant, id: "variant_2", sku: "SOFA-2",
      options: [{ id: "fabric2", option_id: "fabric", value: "Milan 104" }],
    };
    const variants = [first, second];
    expect(productStructuredData({ ...product, variants }, path, production)).toBeNull();
    const group = schema({ ...product, variants, options: [{ id: "fabric", title: "Upholstery" }] });
    expect(group).not.toHaveProperty("variesBy");
    expect(group.hasVariant[0]).toMatchObject({
      name: "Fixture Sofa – AS1687-9",
      additionalProperty: [{ "@type": "PropertyValue", name: "Upholstery", value: "AS1687-9" }],
    });
  });

  it("recognizes finite live made-to-order capacity and treats expired capacity as out of stock", () => {
    const offer = {
      id: "offer", capacity: 4, remaining_capacity: 3, min_lead_time_days: 25, max_lead_time_days: 30,
      observed_at: new Date().toISOString(), expires_at: new Date(Date.now() + 30 * 86_400_000).toISOString(),
    };
    const madeToOrder = (expires_at: string) => ({
      ...variant, inventory_quantity: 0, metadata: { made_to_order_offer: { ...offer, expires_at } },
    });
    expect(schema({ ...product, variants: [madeToOrder(offer.expires_at)] }).offers.availability)
      .toBe("https://schema.org/BackOrder");
    expect(schema({ ...product, variants: [madeToOrder("2023-01-01T00:00:00Z")] }).offers.availability)
      .toBe("https://schema.org/OutOfStock");
  });

  it.each([
    { calculated_price: undefined },
    { calculated_price: { calculated_amount: 100, currency_code: "gbp" } },
    { calculated_price: { calculated_amount: 100.001, currency_code: "zar" } },
    { inventory_quantity: undefined },
  ] satisfies Partial<MedusaVariant>[])("omits offers when visible price or stock is unsupported: %j", (missing) => {
    expect(schema({ ...product, variants: [{ ...variant, ...missing }] })).not.toHaveProperty("offers");
  });

  it("filters private URL shapes without using an unattached attested image", () => {
    const imageUrls = [photo, "https://10.0.0.1/asset.jpg", "https://private.internal/asset.jpg", "https://cdn.example.org/photo.jpg?token=abc"];
    const piece = { ...product, images: imageUrls.map((url) => ({ id: url, url })) };
    expect(schema(piece).image).toEqual([photo]);
    expect(schema({ ...piece, variants: [{ ...variant, metadata: { suitable_image_urls: ["https://cdn.example.org/unattached.jpg"] } }] }))
      .not.toHaveProperty("image");
  });

  it.each([
    { STOREFRONT_INDEXING_ENABLED: "false" },
    { STOREFRONT_PRIVATE_PREVIEW: "on" },
    { RAILWAY_ENVIRONMENT_NAME: "staging" },
    { NEXT_PUBLIC_BASE_URL: "https://www.daskasas.co.za.preview.example" },
  ])("omits structured data outside indexable canonical production: %j", (gates) => {
    expect(productStructuredData(product, path, { ...production, ...gates })).toBeNull();
    expect(productStructuredData({ ...product, status: "draft" }, path, production)).toBeNull();
  });
});
