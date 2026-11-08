import { parsePriceInput } from "@/lib/api";
import { isValidCartonCount } from "@/lib/carton-helpers";

/**
 * Native dialog + Carbon's exact-match check. `image/*` alone is not enough:
 * the file dialog honours the wildcard, then Carbon compares the MIME type and
 * the extension to the accept list literally and marks a PNG `invalidFileType`.
 * Specific types keep that check from rejecting a normal image. The picker
 * below still reads the original file, so a wildcard miss cannot drop it.
 */
export const SKU_PHOTO_ACCEPT = [
  "image/*",
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
  "image/heic",
  "image/heif",
  ".jpg",
  ".jpeg",
  ".png",
  ".webp",
  ".gif",
  ".heic",
  ".heif",
];

const IMAGE_EXTENSIONS = new Set(["jpg", "jpeg", "png", "webp", "gif", "heic", "heif"]);

export type NewSkuFieldInput = {
  ourRef: string;
  name: string;
  design: string;
  fabric: string;
  cartonCount: number | "";
  recordStockNow: boolean;
  openingLocationId: string;
  openingQty: number | "";
  openingUnitCost: string;
};

type FileListLike = ArrayLike<File>;

export function missingNewSkuFields(input: NewSkuFieldInput): string[] {
  const missing: string[] = [];
  if (!input.ourRef.trim()) {
    missing.push("Our ref");
  }
  if (!input.name.trim()) {
    missing.push("Name");
  }
  if (!input.design.trim()) {
    missing.push("Design");
  }
  if (!input.fabric.trim()) {
    missing.push("Fabric");
  }
  if (!isValidCartonCount(input.cartonCount)) {
    missing.push("Cartons");
  }
  if (input.recordStockNow) {
    if (!input.openingLocationId.trim()) {
      missing.push("Location");
    }
    if (
      !(
        typeof input.openingQty === "number" &&
        Number.isFinite(input.openingQty) &&
        input.openingQty >= 1
      )
    ) {
      missing.push("Quantity on hand");
    }
    const cost = parsePriceInput(input.openingUnitCost);
    if (cost === null || cost <= 0) {
      missing.push("Unit cost");
    }
  }
  return missing;
}

export function missingNewSkuMessage(fields: readonly string[]): string | null {
  if (fields.length === 0) {
    return null;
  }
  if (fields.length === 1) {
    return `${fields[0]} is required before you can save.`;
  }
  if (fields.length === 2) {
    return `${fields[0]} and ${fields[1]} are required before you can save.`;
  }
  const head = fields.slice(0, -1).join(", ");
  return `${head}, and ${fields[fields.length - 1]} are required before you can save.`;
}

function listFiles(files: FileListLike | null | undefined): File[] {
  if (!files || typeof files.length !== "number" || files.length === 0) {
    return [];
  }
  return Array.from(files);
}

function filesOn(value: unknown): File[] {
  if (!value || typeof value !== "object" || !("files" in value)) {
    return [];
  }
  return listFiles((value as { files?: FileListLike | null }).files);
}

function fileExtension(name: string): string | null {
  const base = name.trim().split(/[/\\]/).pop() ?? "";
  const dot = base.lastIndexOf(".");
  if (dot <= 0 || dot === base.length - 1) {
    return null;
  }
  return base.slice(dot + 1).toLowerCase();
}

export function skuPhotoError(file: { name: string; type: string; size?: number }): string | null {
  if (file.size === 0) {
    return `"${file.name}" is empty. Choose an image file.`;
  }
  const type = file.type.trim().toLowerCase();
  if (type.startsWith("image/")) {
    return null;
  }
  const extension = fileExtension(file.name);
  if (extension && IMAGE_EXTENSIONS.has(extension)) {
    return null;
  }
  return `"${file.name}" isn't a supported image. Use a JPEG, PNG, or WebP file.`;
}

/**
 * Prefer the browser's original file list. Carbon's drop container can omit a
 * file, or set `invalidFileType`, when `accept` is a wildcard such as
 * `image/*` — including a PNG whose name contains spaces. Those files are
 * still on the change/drop event.
 */
export function pickSkuPhoto(
  event: unknown,
  addedFiles: readonly File[],
): { file: File | null; error: string | null } {
  const record =
    event && typeof event === "object"
      ? (event as { dataTransfer?: unknown; target?: unknown })
      : null;
  const fromDrop = filesOn(record?.dataTransfer);
  const fromInput = filesOn(record?.target);
  const file = fromDrop[0] ?? fromInput[0] ?? addedFiles[0] ?? null;
  if (!file) {
    return {
      file: null,
      error: "No image was added. Choose a JPEG, PNG, or WebP file.",
    };
  }
  const error = skuPhotoError(file);
  if (error) {
    return { file: null, error };
  }
  return { file, error: null };
}
