import { describe, expect, it } from "vitest";
import type { MadeToOrderOffer, MedusaVariant, StoreProduct } from "./medusa";
import { productMetaDescription, productPageCopy, productStructuredData } from "./product-seo";

const origin = "https://www.daskasas.co.za";
const path = "/product/firstout-group-11111111-1111-4111-8111-111111111111";
const publicEnv = {
  NEXT_PUBLIC_BASE_URL: origin,
  RAILWAY_ENVIRONMENT_NAME: "production",
  STOREFRONT_PRIVATE_PREVIEW: "off",
  STOREFRONT_INDEXING_ENABLED: "true",
};

const image = "https://media.example.com/linden-oak.jpg";
const variant: MedusaVariant = {
  id: "variant_linden_oak",
  sku: "LINDEN-OAK",
  material: "Solid oak",
  inventory_quantity: 3,
  calculated_price: { calculated_amount: 4299.95, currency_code: "zar" },
  images: [{ id: "img_oak", url: image }],
  metadata: { dimensions_cm: { width: 135, depth: 38, height: 45, diameter: null } },
};
const product: StoreProduct = {
  id: "prod_linden",
  handle: "firstout-group-11111111-1111-4111-8111-111111111111",
  title: "Linden Bench",
  description: "A slatted oak bench with a low rectangular seat.",
  categories: [{ id: "cat_dining", handle: "dining-room", name: "Dining Room" }],
  variants: [variant],
};

function schema(piece: StoreProduct = product, env = publicEnv) {
  const data = productStructuredData(piece, path, env);
  return data ? JSON.parse(data) : null;
}

function offer(overrides: Partial<MadeToOrderOffer> = {}): MadeToOrderOffer {
  const now = Date.now();
  return {
    id: "offer_linden", capacity: 4, remaining_capacity: 2, min_lead_time_days: 21, max_lead_time_days: 35,
    expires_at: new Date(now + 3600_000).toISOString(), observed_at: new Date(now).toISOString(), ...overrides,
  };
}

describe("product meta descriptions", () => {
  it("prefers a useful published override and renders it as plain text", () => {
    expect(productMetaDescription({
      ...product,
      metadata: { seo_description: "<p>Linden Bench has an oak seat &amp; a low profile.</p>" },
    })).toBe("Linden Bench has an oak seat & a low profile.");
  });

  it("keeps concise editorial copy and skips an override that only repeats the title", () => {
    expect(productMetaDescription({ ...product, metadata: { seo_description: "Hand-finished oak." } }))
      .toBe("Linden Bench. Hand-finished oak.");
    expect(productMetaDescription({ ...product, metadata: { seo_description: "Linden Bench." } }))
      .toBe("Linden Bench. A slatted oak bench with a low rectangular seat. SKU LINDEN-OAK.");
  });

  it("makes generated copy distinct when two catalogue pages share a title and description", () => {
    expect(productMetaDescription(product)).toBe("Linden Bench. A slatted oak bench with a low rectangular seat. SKU LINDEN-OAK.");
    expect(productMetaDescription({
      ...product, id: "prod_linden_ash", variants: [{ ...variant, sku: "LINDEN-ASH" }],
    })).toContain("SKU LINDEN-ASH.");
  });

  it("falls back to published facts when copy is absent or retired", () => {
    expect(productMetaDescription({
      ...product, description: "A considered addition to your living space.", metadata: { seo_description: "   " },
    })).toBe("Explore Linden Bench at DasKasas. Dimensions: 135 × 38 × 45 cm. Material: Solid oak. Dining Room collection. SKU LINDEN-OAK.");
  });

  it("omits incomplete legacy dimensions that the product page does not display", () => {
    expect(productMetaDescription({
      ...product, description: null, length: 100,
      metadata: { dimension_unit: "cm" },
      variants: [{ ...variant, metadata: undefined }],
    })).not.toContain("100 cm");
  });

  it("uses the published diameter and height of a round piece without inventing other dimensions", () => {
    const description = productMetaDescription({
      ...product, title: "Chela Round Dining Table", description: null,
      variants: [{ ...variant, sku: "CHELA", material: null,
        metadata: { dimensions_cm: { diameter: 150, height: 76, width: null, depth: null } } }],
    });
    expect(description).toContain("Dimensions: 150 cm diameter, 76 cm high.");
    expect(description).not.toMatch(/wide|deep/);
  });

  it("includes only shared group measurements alongside visible finish options", () => {
    const dimensions = { diameter: null, width: 120, depth: 60, height: 40 };
    const table = {
      ...product, title: "Kinita Coffee Table", description: null,
      options: [{ id: "finish", title: "Metal finish" }],
      variants: ["Gold", "Silver"].map((value, index) => ({
        ...variant, id: `kinita_${index}`, sku: `KINITA-${index}`,
        options: [{ id: value, option_id: "finish", value }], metadata: { dimensions_cm: dimensions },
      })),
    };
    expect(productMetaDescription(table)).toContain("Dimensions: 120 × 60 × 40 cm. Metal finish: Gold or Silver.");
    const differentDepth = { ...table.variants[1], metadata: { dimensions_cm: { ...dimensions, depth: 65 } } };
    const description = productMetaDescription({ ...table, variants: [table.variants[0], differentDepth] });
    expect(description).toContain("Dimensions: 120 cm wide, 40 cm high. Metal finish: Gold or Silver.");
    expect(description).not.toMatch(/60 cm|65 cm/);
  });

  it("keeps a long upholstery choice list within the description cap using complete facts", () => {
    const description = productMetaDescription({
      ...product, title: "Alexa Dining Chair", description: null,
      options: [{ id: "upholstery", title: "Upholstery" }],
      variants: ["Grey / silver frame", "Navy velvet / silver frame", "White PU / silver frame"].map((value, index) => ({
        ...variant, id: `alexa_${index}`, sku: index === 0 ? "P62129X2" : `ALEXA-${index}`,
        options: [{ id: `choice_${index}`, option_id: "upholstery", value }],
        metadata: { dimensions_cm: { diameter: null, width: 47, depth: 60, height: 91 } },
      })),
    });
    expect(description?.length).toBeLessThanOrEqual(170);
    expect(description).toContain("Dimensions: 47 × 60 × 91 cm.");
    expect(description).toContain("Upholstery: Grey / silver frame, Navy velvet / silver frame or White PU / silver frame.");
    expect(description).toMatch(/SKU P62129X2\.$/);
  });

  it("keeps long generated descriptions compact without losing their identifying SKU", () => {
    const description = productMetaDescription({
      ...product,
      description: "<style>ignore this CSS</style>" + "An oak bench with a rectangular seat and a matte finish. ".repeat(5),
    });
    expect(description?.length).toBeLessThanOrEqual(170);
    expect(description).toContain("Linden Bench");
    expect(description).toMatch(/… SKU LINDEN-OAK\.$/);
    expect(description).not.toContain("ignore this CSS");
  });
});

describe("product page metadata for selected variants", () => {
  it("uses public option values even when the available finish is named by a code", () => {
    const selection = { ...variant, options: [{ id: "fabric_oak", option_id: "fabric", value: "FAB-42" }] };
    const other = { ...variant, id: "other", options: [{ id: "fabric_grey", option_id: "fabric", value: "Grey" }] };
    const group = { ...product, options: [{ id: "fabric", title: "Upholstery" }], variants: [selection, other] };

    expect(productPageCopy(group)).toEqual({ title: group.title, description: productMetaDescription(group) });
    expect(productPageCopy(group, selection)).toEqual({
      title: "Linden Bench – FAB-42",
      description: "Linden Bench. Upholstery: FAB-42. SKU LINDEN-OAK.",
    });
    expect(productPageCopy(product, variant)).toEqual(productPageCopy(product));
  });
});

describe("product structured data", () => {
  it("uses the canonical page, listed exact ZAR price and the approved attached image order", () => {
    const relative = "/catalogue/linden-alt.jpg";
    const source = {
      ...variant,
      images: [...variant.images ?? [], { id: "alt", url: relative }],
      metadata: { suitable_image_urls: [relative, "https://media.example.com/unattached.jpg", image] },
    };
    expect(schema({ ...product, variants: [source] })).toMatchObject({
      "@context": "https://schema.org", "@type": "Product", name: "Linden Bench",
      sku: "LINDEN-OAK", url: origin + path, description: product.description,
      image: [origin + relative, image], material: variant.material,
      offers: { "@type": "Offer", url: origin + path, price: 4299.95, priceCurrency: "ZAR", availability: "https://schema.org/InStock" },
    });
  });

  it("only exposes images on public HTTPS URLs and omits previews, signed links and demo placeholders", () => {
    const urls = [
      "https://files.railway.internal/image.jpg", "https://127.0.0.1/image.jpg",
      "https://media.example.com/image.jpg?secret=example", "https://user:pass@media.example.com/image.jpg",
      "http://media.example.com/image.jpg", "//media.example.com/image.jpg", "/demo/arc-front.jpg",
      image,
    ];
    expect(schema({ ...product, variants: [{ ...variant, images: urls.map((url) => ({ id: url, url })) }] }).image)
      .toEqual([image]);
  });

  it("uses the canonical group and exact variant selectors with per-variant images, price and availability", () => {
    const ashImage = "https://media.example.com/linden-ash.jpg";
    const choices = (value: string) => [{ id: `color_${value}`, option_id: "finish", value }];
    const group = {
      ...product,
      options: [{ id: "finish", title: "Colour" }],
      variants: [
        { ...variant, options: choices("Natural") },
        { ...variant, id: "variant_linden_ash", sku: "LINDEN-ASH", options: choices("Grey"),
          calculated_price: { calculated_amount: 4499, currency_code: "zar" }, inventory_quantity: 0,
          images: [{ id: "img_ash", url: ashImage }], metadata: { made_to_order_offer: offer() } },
      ],
    };
    const output = schema(group);
    expect(output).toMatchObject({ "@type": "ProductGroup", url: origin + path,
      productGroupID: product.id, variesBy: ["https://schema.org/color"] });
    expect(output).not.toHaveProperty("offers");
    expect(output.hasVariant).toMatchObject([
      { name: "Linden Bench – Natural", color: "Natural", sku: "LINDEN-OAK", url: `${origin}${path}?variant=variant_linden_oak`, image: [image], offers: { price: 4299.95 } },
      { name: "Linden Bench – Grey", color: "Grey", sku: "LINDEN-ASH", url: `${origin}${path}?variant=variant_linden_ash`, image: [ashImage], offers: { price: 4499, availability: "https://schema.org/BackOrder" } },
    ]);
  });

  it.each([
    ["Upholstery colour", "color"],
    ["Upholstery color", "color"],
    ["Upholstery material", "material"],
    ["Upholstery", null],
    ["Metal finish", null],
  ] as const)("uses schema attributes only for an unambiguous %s axis", (title, property) => {
    const result = schema({
      ...product, options: [{ id: "textile", title }],
      variants: ["Option A", "Option B"].map((value, index) => ({
        ...variant, id: `textile_${index}`, sku: `TEXTILE-${index}`, material: null,
        options: [{ id: `textile_choice_${index}`, option_id: "textile", value }],
      })),
    });
    expect(result.hasVariant[0].name).toContain("Option A");
    if (property) {
      expect(result.variesBy).toEqual([`https://schema.org/${property}`]);
      expect(result.hasVariant[0][property]).toBe("Option A");
    } else {
      expect(result).not.toHaveProperty("variesBy");
      expect(result.hasVariant[0]).not.toHaveProperty("color");
      expect(result.hasVariant[0]).not.toHaveProperty("material");
      expect(result.hasVariant[0].additionalProperty).toEqual([{ "@type": "PropertyValue", name: title, value: "Option A" }]);
    }
  });

  it("omits variant markup when shoppers have no varying option to select", () => {
    expect(schema({ ...product, variants: [variant, { ...variant, id: "variant_linden_ash", sku: "LINDEN-ASH" }] })).toBeNull();
  });

  it("reports known zero stock without treating stale made-to-order capacity as available", () => {
    const zeroStock = { ...variant, inventory_quantity: 0, metadata: {
      made_to_order_offer: offer({ observed_at: new Date(Date.now() - 6 * 60_000).toISOString() }),
    } };
    expect(schema({ ...product, variants: [zeroStock] }).offers).toMatchObject({
      price: 4299.95, priceCurrency: "ZAR", availability: "https://schema.org/OutOfStock",
    });
  });

  it.each([
    { calculated_price: undefined },
    { calculated_price: { calculated_amount: 4299.95, currency_code: "USD" } },
    { calculated_price: { calculated_amount: 4299.95, currency_code: "" } },
    { calculated_price: { calculated_amount: 0, currency_code: "zar" } },
    { calculated_price: { calculated_amount: 4299.951, currency_code: "zar" } },
    { inventory_quantity: undefined },
    { inventory_quantity: -1 },
    { inventory_quantity: 0, metadata: { made_to_order_offer: offer({ max_lead_time_days: 0 }) } },
    { sku: null },
  ])("omits Offer when price, SKU or availability are unverified (%o)", (overrides) => {
    expect(schema({ ...product, variants: [{ ...variant, ...overrides }] })).not.toHaveProperty("offers");
  });

  it("does not inject schema into noindex, preview, nonproduction or noncanonical pages", () => {
    expect(schema(product, { ...publicEnv, STOREFRONT_INDEXING_ENABLED: "false" })).toBeNull();
    expect(schema(product, { ...publicEnv, STOREFRONT_PRIVATE_PREVIEW: "on" })).toBeNull();
    expect(schema(product, { ...publicEnv, RAILWAY_ENVIRONMENT_NAME: "preview" })).toBeNull();
    expect(schema(product, { ...publicEnv, NEXT_PUBLIC_BASE_URL: "https://daskasas.co.za" })).toBeNull();
    expect(schema({ ...product, status: "draft" })).toBeNull();
    expect(productStructuredData(product, "/product/../account", publicEnv)).toBeNull();
  });

  it("safely escapes script-sensitive characters in the public product copy", () => {
    const title = "Oak < 90° Bench";
    const output = productStructuredData({ ...product, title }, path, publicEnv);
    expect(output).toContain("\\u003c");
    expect(output).not.toContain("<");
    expect(JSON.parse(output ?? "null").name).toBe(title);
  });
});
