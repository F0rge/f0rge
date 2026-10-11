import {
  CATALOGUE_COLLECTION_HANDLE, CATALOGUE_COLLECTION_TITLE, DINING_ROOM_COLLECTION_HANDLE, LEGACY_CATALOGUE_COLLECTION_HANDLE,
  ROOM_COLLECTIONS_METADATA_KEY, SOFAS_COLLECTION_HANDLE, collectionEnsurePlan, roomCollectionHandles, withRoomCollections,
} from "./catalogue-collections";

const catalogue: [string, string, "" | "sofas" | "dining-room"][] = [
  ["PG-ARMCHAIR", "Playground armchair", ""],
  ["PG-BOOKCASE", "Playground bookcase", ""],
  ["PG-CHAIR", "Playground dining chair", "dining-room"],
  ["PG-COFFEE", "Playground coffee table", ""],
  ["PG-LAMP", "Playground floor lamp", ""],
  ["PG-OTTOMAN", "Playground ottoman", ""],
  ["PG-SIDEBOARD", "Playground sideboard", "dining-room"],
  ["PG-SOFA", "Playground 3-seater sofa", "sofas"],
  ["PG-TABLE", "Playground dining table", "dining-room"],
  ["VEL-BI-ACC-01", "Kilim floor cushion", ""],
  ["VEL-BI-ACC-02", "Mohair throw sand", ""],
  ["VEL-BI-ACC-03", "Murano amber vase", ""],
  ["VEL-BI-ACC-04", "Travertine bowl", ""],
  ["VEL-BI-ACC-05", "Ceramic vessel set", ""],
  ["VEL-BI-ACC-06", "Walnut tray", ""],
  ["VEL-BI-ACC-07", "Leather ottoman cube", ""],
  ["VEL-BI-ACC-08", "Mirror sunburst 120", ""],
  ["VEL-BI-ACC-09", "Last-season neon sculpture", ""],
  ["VEL-BI-ACC-10", "Alpaca throw charcoal", ""],
  ["VEL-BI-ACC-11", "Marble bookends pair", ""],
  ["VEL-BI-ACC-12", "Woven wall hanging", ""],
  ["VEL-BI-BED-01", "Lucca king bed", ""],
  ["VEL-BI-BED-02", "Siena queen bed", ""],
  ["VEL-BI-BED-03", "Como platform king", ""],
  ["VEL-BI-BED-04", "Karoo oak bed", ""],
  ["VEL-BI-BED-05", "Drakensberg storage bed", ""],
  ["VEL-BI-BED-06", "Winelands four-poster", ""],
  ["VEL-BI-BED-07", "Sandton winged king", ""],
  ["VEL-BI-BED-08", "Brooklyn low bed", ""],
  ["VEL-BI-BED-09", "Waterkloof upholstered", ""],
  ["VEL-BI-BED-10", "Menlyn rattan bed", ""],
  ["VEL-BI-BED-11", "Hyde Park leather bed", ""],
  ["VEL-BI-BED-12", "Parktown queen", ""],
  ["VEL-BI-CTB-01", "Carrara nest pair", ""],
  ["VEL-BI-CTB-02", "Travertine coffee table", ""],
  ["VEL-BI-CTB-03", "Oak drum coffee table", ""],
  ["VEL-BI-CTB-04", "Walnut side table", ""],
  ["VEL-BI-CTB-05", "Brass drinks table", ""],
  ["VEL-BI-CTB-06", "Concrete coffee block", ""],
  ["VEL-BI-CTB-07", "Glass waterfall table", ""],
  ["VEL-BI-CTB-08", "Rattan side table", ""],
  ["VEL-BI-CTB-09", "Pietra coffee oval", ""],
  ["VEL-BI-CTB-10", "Parkhurst nesting trio", ""],
  ["VEL-BI-CTB-11", "Sandton console", ""],
  ["VEL-BI-CTB-12", "Linden live-edge table", ""],
  ["VEL-BI-DCH-01", "Asti dining chair", "dining-room"],
  ["VEL-BI-DCH-02", "Alba dining chair", "dining-room"],
  ["VEL-BI-DCH-03", "Barolo dining chair", "dining-room"],
  ["VEL-BI-DCH-04", "Chianti side chair", "dining-room"],
  ["VEL-BI-DCH-05", "Stellenbosch dining chair", "dining-room"],
  ["VEL-BI-DCH-06", "Franschhoek carver", "dining-room"],
  ["VEL-BI-DCH-07", "Constantia dining chair", "dining-room"],
  ["VEL-BI-DCH-08", "Kramerville stool chair", "dining-room"],
  ["VEL-BI-DCH-09", "Milano cane chair", "dining-room"],
  ["VEL-BI-DCH-10", "Como bentwood chair", "dining-room"],
  ["VEL-BI-DCH-11", "Parkhurst dining chair", "dining-room"],
  ["VEL-BI-DCH-12", "Sandton host chair", "dining-room"],
  ["VEL-BI-DTB-01", "Asti oak dining table 240", "dining-room"],
  ["VEL-BI-DTB-02", "Alba round dining table", "dining-room"],
  ["VEL-BI-DTB-03", "Barolo walnut table 280", "dining-room"],
  ["VEL-BI-DTB-04", "Stellenbosch farm table", "dining-room"],
  ["VEL-BI-DTB-05", "Franschhoek extendable", "dining-room"],
  ["VEL-BI-DTB-06", "Constantia marble table", "dining-room"],
  ["VEL-BI-DTB-07", "Parkhurst 8-seater", "dining-room"],
  ["VEL-BI-DTB-08", "Melville compact table", "dining-room"],
  ["VEL-BI-DTB-09", "Waterkloof glass table", "dining-room"],
  ["VEL-BI-DTB-10", "Illovo ceramic table", "dining-room"],
  ["VEL-BI-LMP-01", "Arco floor lamp", ""],
  ["VEL-BI-LMP-02", "Fontana table lamp", ""],
  ["VEL-BI-LMP-03", "Castiglioni pendant", ""],
  ["VEL-BI-LMP-04", "Kramerville tripod lamp", ""],
  ["VEL-BI-LMP-05", "Murano cluster pendant", ""],
  ["VEL-BI-LMP-06", "Paper lantern trio", ""],
  ["VEL-BI-LMP-07", "Brass picture light", ""],
  ["VEL-BI-LMP-08", "Alabaster wall sconce pair", ""],
  ["VEL-BI-LMP-09", "Overberg rattan pendant", ""],
  ["VEL-BI-LMP-10", "Last-season chrome floor", ""],
  ["VEL-BI-LMP-11", "Parkhurst ceramic lamp", ""],
  ["VEL-BI-LMP-12", "Sandton chandelier 12-light", ""],
  ["VEL-BI-OUT-01", "Clifton sling sofa", "sofas"],
  ["VEL-BI-OUT-02", "Hermanus teak dining", "dining-room"],
  ["VEL-BI-OUT-03", "Plett lounge set", ""],
  ["VEL-BI-OUT-04", "Camps Bay daybed", ""],
  ["VEL-BI-OUT-05", "Knysna dining chairs pair", "dining-room"],
  ["VEL-BI-OUT-06", "Umhlanga sun lounger", ""],
  ["VEL-BI-OUT-07", "Hartbeespoort leftover set", ""],
  ["VEL-BI-OUT-08", "Magaliesberg bar set", ""],
  ["VEL-BI-OUT-09", "Ballito rope sofa", "sofas"],
  ["VEL-BI-OUT-10", "Irene outdoor dining", "dining-room"],
  ["VEL-BI-OUT-11", "Bryanston fire table", ""],
  ["VEL-BI-OUT-12", "Fourways parasol", ""],
  ["VEL-BI-SOF-02", "Bergamo 3-seater", "sofas"],
  ["VEL-BI-SOF-03", "Lecce modular corner", "sofas"],
  ["VEL-BI-SOF-04", "Torino leather 3-seater", "sofas"],
  ["VEL-BI-SOF-05", "Parma deep-seat", "sofas"],
  ["VEL-BI-SOF-06", "Siena 2-seater", "sofas"],
  ["VEL-BI-SOF-07", "Ravenna chaise", ""],
  ["VEL-BI-SOF-08", "Udine lounge", "sofas"],
  ["VEL-BI-SOF-09", "Treviso curved sofa", "sofas"],
  ["VEL-BI-SOF-10", "Vicenza club sofa", "sofas"],
  ["VEL-BI-SOF-11", "Padova linen 3-seater", "sofas"],
  ["VEL-BI-SOF-12", "Livorno modular 4-seat", "sofas"],
  ["VEL-BI-SOF-13", "Perugia slipcover sofa", "sofas"],
  ["VEL-BI-SOF-14", "Trento compact 2-seater", "sofas"],
  ["VEL-BI-SOF-15", "Bolzano leather lounge", "sofas"],
  ["VEL-BI-SOF-16", "Modena family sofa", "sofas"],
  ["VEL-BI-SOF-17", "Rimini last-season sofa", "sofas"],
  ["VEL-BI-SOF-18", "Ancona L-shape", "sofas"],
  ["VEL-BI-SOF-19", "Pescara daybed", ""],
  ["VEL-BI-SOF-20", "Salerno 3-seater", "sofas"],
  ["VEL-BI-SOF-21", "Bari bouclé 2-seater", "sofas"],
  ["VEL-BI-SOF-22", "Catania sectional XL", "sofas"],
  ["VEL-BI-STO-01", "Verona sideboard 200", "dining-room"],
  ["VEL-BI-STO-02", "Bergamo dresser", ""],
  ["VEL-BI-STO-03", "Kramerville bookcase", ""],
  ["VEL-BI-STO-04", "Ethnicraft TV unit", ""],
  ["VEL-BI-STO-05", "Parkhurst tallboy", ""],
  ["VEL-BI-STO-06", "Leftover high-gloss cabinet", ""],
  ["VEL-BI-V1", "Verona sectional", "sofas"],
  ["VEL-CHAIR-CLUB", "Club armchair", ""],
  ["VEL-SOFA-BOUCLE", "Como 2-seater", "sofas"],
  ["VEL-SOFA-CHAISE", "Capri chaise", ""],
  ["VEL-SOFA-CHARCOAL", "Deep-seat 3-seater", "sofas"],
  ["VEL-SOFA-CHESTER", "Chesterfield 3-seater", "sofas"],
  ["VEL-SOFA-CLOUD", "Cloud modular 4-seat", "sofas"],
  ["VEL-SOFA-CURVE", "Arc curved sofa", "sofas"],
  ["VEL-SOFA-LONDON", "London 3-seater", "sofas"],
  ["VEL-SOFA-LSHAPE", "Milano L-shape", "sofas"],
  ["VEL-SOFA-SAND", "Sand modular corner", "sofas"],
  ["VEL-SOFA-TEAK", "Palma outdoor sofa", "sofas"],
  ["VEL-SOFA-WALNUT", "Kinfolk lounge", "sofas"],
  ["123123", "David", ""],
  ["VEL-TABLE-MARBLE", "Carrara marble coffee table", ""],
];

test("room collections follow the title and SKU, and a piece is never in both", () => {
  const mismatches = catalogue.flatMap(([sku, title, expected]) => {
    const handles = roomCollectionHandles(title, [sku]);
    const actual = handles[0] || "";
    return actual === expected && handles.length <= 1 ? [] : [`${sku} ${title}: ${actual || "none"}`];
  });
  expect(mismatches).toEqual([]);
  expect(catalogue.filter((row) => row[2] === "sofas")).toHaveLength(33);
  expect(catalogue.filter((row) => row[2] === "dining-room")).toHaveLength(29);
  expect(roomCollectionHandles("Capri chaise sofa", ["VEL-SOFA-CHAISE"])).toEqual([SOFAS_COLLECTION_HANDLE]);
  expect(roomCollectionHandles("Ravenna chaise", ["VEL-BI-SOF-07"])).toEqual([]);
  expect(roomCollectionHandles("Pescara daybed", ["VEL-BI-SOF-19"])).toEqual([]);
  expect(roomCollectionHandles("Carrara marble coffee table", ["VEL-TABLE-MARBLE"])).toEqual([]);
});

test("On Sale renames the old in-stock collection in place", () => {
  expect(CATALOGUE_COLLECTION_HANDLE).toBe("on-sale");
  expect(CATALOGUE_COLLECTION_TITLE).toBe("On Sale");
  expect(LEGACY_CATALOGUE_COLLECTION_HANDLE).toBe("in-stock");
  expect(DINING_ROOM_COLLECTION_HANDLE).toBe("dining-room");
  const legacy = { id: "pcol_sale", handle: "in-stock", title: "In stock" };
  expect(collectionEnsurePlan([legacy], CATALOGUE_COLLECTION_HANDLE, CATALOGUE_COLLECTION_TITLE, LEGACY_CATALOGUE_COLLECTION_HANDLE))
    .toEqual({ action: "rename", id: "pcol_sale" });
  expect(collectionEnsurePlan(
    [{ id: "pcol_sale", handle: "on-sale", title: "On Sale" }, legacy],
    CATALOGUE_COLLECTION_HANDLE, CATALOGUE_COLLECTION_TITLE, LEGACY_CATALOGUE_COLLECTION_HANDLE,
  )).toEqual({ action: "keep", id: "pcol_sale" });
  expect(collectionEnsurePlan(
    [{ id: "pcol_sale", handle: "on-sale", title: "Sale" }],
    CATALOGUE_COLLECTION_HANDLE, CATALOGUE_COLLECTION_TITLE,
  )).toEqual({ action: "retitle", id: "pcol_sale" });
  expect(collectionEnsurePlan([], SOFAS_COLLECTION_HANDLE, "Sofas")).toEqual({ action: "create" });
});

test("room membership keeps the rest of the product metadata", () => {
  const metadata = { source_product_group_id: "group-1", storefront_room_collections: ["sofas"] };
  expect(withRoomCollections(metadata, ["sofas"])).toBeNull();
  expect(withRoomCollections({ source_product_group_id: "group-1" }, ["dining-room"])).toEqual({
    source_product_group_id: "group-1",
    [ROOM_COLLECTIONS_METADATA_KEY]: ["dining-room"],
  });
  expect(withRoomCollections(metadata, [])).toEqual({
    source_product_group_id: "group-1",
    [ROOM_COLLECTIONS_METADATA_KEY]: [],
  });
  expect(withRoomCollections(null, [])).toBeNull();
});
