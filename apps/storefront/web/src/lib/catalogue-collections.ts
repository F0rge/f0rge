export const SOFAS_COLLECTION_HANDLE = "sofas";
export const DINING_ROOM_COLLECTION_HANDLE = "dining-room";

const ROOM_COLLECTION_TITLES: Record<string, string> = {
  [SOFAS_COLLECTION_HANDLE]: "Sofas",
  [DINING_ROOM_COLLECTION_HANDLE]: "Dining Room",
};

const ROOM_HANDLES = new Set(Object.keys(ROOM_COLLECTION_TITLES));

export type StoreCollection = { id: string; title: string; handle: string };

type ProductCollections = {
  collection?: StoreCollection | null;
  metadata?: { storefront_room_collections?: unknown } | null;
};

export function roomCollectionHandles(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const handles: string[] = [];
  for (const item of value) {
    if (typeof item === "string" && ROOM_HANDLES.has(item) && !handles.includes(item)) handles.push(item);
  }
  return handles;
}

export function productInCollection(product: ProductCollections, handle: string): boolean {
  return product.collection?.handle === handle || roomCollectionHandles(product.metadata?.storefront_room_collections).includes(handle);
}

export function merchandisingCollections(products: ProductCollections[]): StoreCollection[] {
  const collections = new Map<string, StoreCollection>();
  for (const product of products) {
    if (product.collection) {
      collections.set(product.collection.handle, {
        id: product.collection.id, title: product.collection.title, handle: product.collection.handle,
      });
    }
    for (const handle of roomCollectionHandles(product.metadata?.storefront_room_collections)) {
      if (!collections.has(handle)) collections.set(handle, { id: handle, title: ROOM_COLLECTION_TITLES[handle], handle });
    }
  }
  return [...collections.values()];
}
