export const CATALOGUE_COLLECTION_HANDLE = "on-sale";
export const CATALOGUE_COLLECTION_TITLE = "On Sale";
export const LEGACY_CATALOGUE_COLLECTION_HANDLE = "in-stock";

export const SOFAS_COLLECTION_HANDLE = "sofas";
export const SOFAS_COLLECTION_TITLE = "Sofas";
export const DINING_ROOM_COLLECTION_HANDLE = "dining-room";
export const DINING_ROOM_COLLECTION_TITLE = "Dining Room";

export const ROOM_COLLECTIONS_METADATA_KEY = "storefront_room_collections";

export const ROOM_COLLECTIONS = [
  { handle: SOFAS_COLLECTION_HANDLE, title: SOFAS_COLLECTION_TITLE },
  { handle: DINING_ROOM_COLLECTION_HANDLE, title: DINING_ROOM_COLLECTION_TITLE },
] as const;

export type CollectionRecord = { id: string; handle: string; title: string };

export type CollectionEnsurePlan =
  | { action: "keep"; id: string }
  | { action: "retitle"; id: string }
  | { action: "rename"; id: string }
  | { action: "create" };

const SOFA_WORDS = ["sofa", "sofas", "sectional", "sectionals", "l-shape", "l shape"];
const NOT_SOFA_WORDS = ["chair", "chairs", "bed", "beds", "daybed", "daybeds", "chaise", "chaises"];
const NOT_DINING_WORDS = [
  "bed", "beds", "daybed", "daybeds", "lamp", "lamps", "light", "lights",
  "sconce", "sconces", "pendant", "pendants", "chandelier", "chandeliers",
  "sofa", "sofas", "sectional", "sectionals", "chaise", "chaises",
];

function text(value: string): string {
  return value.toLocaleLowerCase("en");
}

function hasWord(value: string, words: string[]): boolean {
  return words.some((word) => {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/ /g, "\\s+");
    return new RegExp(`(?:^|[^a-z0-9])${escaped}(?:$|[^a-z0-9])`, "i").test(value);
  });
}

function skuIsSofa(sku: string): boolean {
  return sku.startsWith("vel-sofa-") || sku.startsWith("vel-bi-sof-") || sku === "pg-sofa" || sku === "vel-bi-v1";
}

function skuIsDiningTableOrChair(sku: string): boolean {
  return sku.startsWith("vel-bi-dtb-") || sku.startsWith("vel-bi-dch-") || sku === "pg-table" || sku === "pg-chair";
}

function skuIsNotDining(sku: string): boolean {
  return sku.startsWith("vel-bi-lmp-") || sku.startsWith("vel-bi-bed-") || sku.startsWith("vel-bi-ctb-")
    || sku.startsWith("vel-bi-sof-") || sku.startsWith("vel-bi-acc-") || sku.startsWith("vel-sofa-")
    || sku === "pg-lamp" || sku === "pg-coffee" || sku === "pg-sofa" || sku === "pg-ottoman"
    || sku === "pg-armchair" || sku === "pg-bookcase" || sku === "vel-table-marble"
    || sku === "vel-chair-club" || sku === "vel-bi-v1";
}

export function isSofaPiece(title: string, skus: string[]): boolean {
  const name = text(title);
  const codes = skus.map(text);
  if (hasWord(name, SOFA_WORDS)) return true;
  if (hasWord(name, NOT_SOFA_WORDS)) return false;
  return codes.some(skuIsSofa);
}

export function isDiningRoomPiece(title: string, skus: string[]): boolean {
  const name = text(title);
  const codes = skus.map(text);
  if (isSofaPiece(name, codes)) return false;
  if (codes.some(skuIsDiningTableOrChair)) return true;
  if (codes.some(skuIsNotDining)) return false;
  if (hasWord(name, NOT_DINING_WORDS)) return false;
  if (hasWord(name, ["sideboard", "sideboards"])) return true;
  return hasWord(name, ["dining"]);
}

export function roomCollectionHandles(title: string, skus: string[]): string[] {
  if (isSofaPiece(title, skus)) return [SOFAS_COLLECTION_HANDLE];
  if (isDiningRoomPiece(title, skus)) return [DINING_ROOM_COLLECTION_HANDLE];
  return [];
}

export function roomHandlesEqual(current: unknown, next: readonly string[]): boolean {
  const values = Array.isArray(current) ? current.filter((item): item is string => typeof item === "string") : [];
  return values.length === next.length && values.every((value, index) => value === next[index]);
}

export function withRoomCollections(
  metadata: Record<string, unknown> | null | undefined,
  handles: readonly string[],
): Record<string, unknown> | null {
  if (roomHandlesEqual(metadata?.[ROOM_COLLECTIONS_METADATA_KEY], handles)) return null;
  return { ...(metadata || {}), [ROOM_COLLECTIONS_METADATA_KEY]: [...handles] };
}

export function collectionEnsurePlan(
  rows: CollectionRecord[],
  handle: string,
  title: string,
  legacyHandle?: string,
): CollectionEnsurePlan {
  const current = rows.find((row) => row.handle === handle);
  if (current) return current.title === title ? { action: "keep", id: current.id } : { action: "retitle", id: current.id };
  const legacy = legacyHandle ? rows.find((row) => row.handle === legacyHandle) : undefined;
  if (legacy) return { action: "rename", id: legacy.id };
  return { action: "create" };
}
