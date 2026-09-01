import type { Sku } from "@/lib/api";

export const SAME_CODE_COOLDOWN_MS = 1000;

const PREFERRED_FORMATS = [
  "code_128",
  "ean_13",
  "ean_8",
  "upc_a",
  "upc_e",
  "qr_code",
] as const;

export type DetectedBarcode = {
  rawValue: string;
  format: string;
};

export type BarcodeDetectorLike = {
  detect: (source: ImageBitmapSource) => Promise<DetectedBarcode[]>;
};

type BarcodeDetectorCtor = {
  new (options?: { formats?: string[] }): BarcodeDetectorLike;
  getSupportedFormats?: () => Promise<string[]>;
};

export type TillScanError = "unknown" | "no_retail" | "not_on_floor" | "over_floor";

export type TillScanResult =
  | { ok: true; sku: Sku; qty: number }
  | { ok: false; error: TillScanError };

function nativeCtor(): BarcodeDetectorCtor | undefined {
  if (typeof globalThis === "undefined") {
    return undefined;
  }
  return (globalThis as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector;
}

async function tryNativeDetector(): Promise<BarcodeDetectorLike | null> {
  const Ctor = nativeCtor();
  if (!Ctor?.getSupportedFormats) {
    return null;
  }
  try {
    const supported = await Ctor.getSupportedFormats();
    if (!supported.includes("code_128")) {
      return null;
    }
    const formats = PREFERRED_FORMATS.filter((format) => supported.includes(format));
    const detector = new Ctor({ formats });
    const probe = document.createElement("canvas");
    probe.width = 2;
    probe.height = 2;
    await detector.detect(probe);
    return detector;
  } catch {
    return null;
  }
}

async function loadPonyfillDetector(): Promise<BarcodeDetectorLike> {
  const { BarcodeDetector } = await import("barcode-detector/ponyfill");
  return new BarcodeDetector({
    formats: [...PREFERRED_FORMATS],
  });
}

export async function createBarcodeDetector(): Promise<BarcodeDetectorLike> {
  const native = await tryNativeDetector();
  if (native) {
    return native;
  }
  return loadPonyfillDetector();
}

export function tillScanErrorMessage(error: TillScanError): string {
  switch (error) {
    case "unknown":
      return "Unknown barcode.";
    case "no_retail":
      return "No retail price for this SKU.";
    case "not_on_floor":
      return "Not on this floor.";
    case "over_floor":
      return "Not enough stock on the floor.";
    default:
      return "Could not add scanned item.";
  }
}

export function resolveTillScan(options: {
  code: string;
  skus: Sku[];
  allowOurRef: boolean;
  addQty: number;
  floorOnHand: (skuId: string) => number;
  cartQty: (skuId: string) => number;
}): TillScanResult {
  const code = options.code.trim();
  if (!code || options.addQty <= 0) {
    return { ok: false, error: "unknown" };
  }

  const sku =
    options.skus.find((item) => item.our_barcode === code) ??
    (options.allowOurRef ? options.skus.find((item) => item.our_ref === code) : undefined);

  if (!sku) {
    return { ok: false, error: "unknown" };
  }
  if (!sku.retail_ex_vat) {
    return { ok: false, error: "no_retail" };
  }

  const onHand = options.floorOnHand(sku.id);
  if (onHand <= 0) {
    return { ok: false, error: "not_on_floor" };
  }

  const remaining = onHand - options.cartQty(sku.id);
  if (options.addQty > remaining) {
    return { ok: false, error: "over_floor" };
  }

  return { ok: true, sku, qty: options.addQty };
}

export function isDesktopPointer(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.matchMedia("(hover: hover) and (pointer: fine)").matches;
}

export function isQtyOrDiscountField(el: Element | null): boolean {
  if (!el) {
    return false;
  }
  const input =
    el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement
      ? el
      : el.closest("input, textarea");
  if (!input) {
    return false;
  }
  const id = input.id;
  return id === "till-qty" || id.startsWith("cart-qty-") || id.startsWith("cart-discount-");
}

export function isProtectedScanField(el: Element | null): boolean {
  if (!el) {
    return false;
  }
  if (isQtyOrDiscountField(el)) {
    return true;
  }
  // Carbon ComboBox may use a downshift-generated input id — treat any field as owned.
  return Boolean(el.closest("input, textarea, select, [contenteditable='true']"));
}
