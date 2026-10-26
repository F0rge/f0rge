export type Cin7RunMode = "dry_run" | "commit";
export type Cin7RunStatus = "queued" | "running" | "completed" | "failed";

export type Cin7RunSnapshot = {
  mode: Cin7RunMode;
  status: Cin7RunStatus;
  error_count: number;
  file_sha256: string;
};

export type NamedFile = {
  name: string;
  size: number;
  lastModified: number;
};

export function canSeeCin7Import(permissions: readonly string[] | undefined): boolean {
  return permissions?.includes("users.manage") === true;
}

export function fileSelectionKey(files: readonly NamedFile[]): string {
  return files.map((file) => `${file.name}:${file.size}:${file.lastModified}`).join("|");
}

export function isActiveRun(status: Cin7RunStatus): boolean {
  return status === "queued" || status === "running";
}

/** Why Commit stays disabled. Null means the dry run may be committed. */
export function commitBlockedReason(
  run: Cin7RunSnapshot | null,
  selectedKey: string,
  uploadedKey: string,
): string | null {
  if (!run) {
    return "Run a dry run first";
  }
  if (!selectedKey || selectedKey !== uploadedKey) {
    return "The selected file does not match the dry run";
  }
  if (run.mode !== "dry_run") {
    return "Commit a dry run, not another commit";
  }
  if (isActiveRun(run.status)) {
    return "Dry run is still running";
  }
  if (run.status === "failed" || run.error_count > 0) {
    return "Dry run had errors";
  }
  if (run.status !== "completed") {
    return "Dry run did not complete";
  }
  return null;
}

export type HeadlineCounts = {
  skusUpdated: number;
  customersUpdated: number;
  priceListsCreated: number;
  priceListItemsCreated: number;
  generatedBarcodes: number;
  generatedBarcodesBlank: number;
  generatedBarcodesShared: number;
};

type EntityCounts = {
  created: number;
  updated: number;
  unchanged: number;
  skipped: number;
};

export function importHeadlines(summary: {
  entities: Record<string, EntityCounts | undefined>;
  generated_barcodes?: number;
  generated_barcodes_blank?: number;
  generated_barcodes_shared?: number;
}): HeadlineCounts {
  const count = (name: string, field: keyof EntityCounts) => summary.entities[name]?.[field] ?? 0;
  return {
    skusUpdated: count("sku", "updated"),
    customersUpdated: count("customer", "updated"),
    priceListsCreated: count("price_list", "created"),
    priceListItemsCreated: count("price_list_item", "created"),
    generatedBarcodes: summary.generated_barcodes ?? 0,
    generatedBarcodesBlank: summary.generated_barcodes_blank ?? 0,
    generatedBarcodesShared: summary.generated_barcodes_shared ?? 0,
  };
}

export function groupThousands(value: number): string {
  return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function generatedBarcodeHeadline(
  count: number,
  blank: number,
  shared: number,
): string {
  return `${groupThousands(count)} SKUs would get a generated barcode (${groupThousands(blank)} blank, ${groupThousands(shared)} shared)`;
}

export function warningsCsvPath(id: string): string {
  return `/api/v1/cin7-imports/${id}/warnings.csv`;
}

export function barcodesCsvPath(id: string): string {
  return `/api/v1/cin7-imports/${id}/barcodes.csv`;
}

export function errorsCsvPath(id: string): string {
  return `/api/v1/cin7-imports/${id}/errors.csv`;
}

export function appendCin7Files(formData: FormData, files: readonly File[]): void {
  if (files.length === 1 && files[0].name.toLowerCase().endsWith(".zip")) {
    formData.append("file", files[0]);
    return;
  }
  for (const file of files) {
    formData.append("files", file);
  }
}
