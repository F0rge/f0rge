import { describe, expect, it } from "vitest";
import { merchandisingCollections, productInCollection, roomCollectionHandles } from "./catalogue-collections";

const sale = { id: "pcol_sale", title: "On Sale", handle: "on-sale" };

describe("storefront room collections", () => {
  it("keeps On Sale on the product collection and rooms in metadata", () => {
    const sofa = { collection: sale, metadata: { storefront_room_collections: ["sofas", "not-a-room"] } };
    const dining = { collection: sale, metadata: { storefront_room_collections: ["dining-room"] } };
    const lamp = { collection: sale, metadata: { storefront_room_collections: [] } };
    expect(roomCollectionHandles(sofa.metadata.storefront_room_collections)).toEqual(["sofas"]);
    expect(productInCollection(sofa, "on-sale")).toBe(true);
    expect(productInCollection(sofa, "sofas")).toBe(true);
    expect(productInCollection(sofa, "dining-room")).toBe(false);
    expect(productInCollection(dining, "dining-room")).toBe(true);
    expect(productInCollection(lamp, "sofas")).toBe(false);
    const collections = merchandisingCollections([sofa, dining, lamp]).sort((a, b) => a.title.localeCompare(b.title));
    expect(collections.map((collection) => collection.title)).toEqual(["Dining Room", "On Sale", "Sofas"]);
    expect(collections.find((collection) => collection.handle === "on-sale")?.id).toBe("pcol_sale");
  });
});
