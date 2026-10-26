import { describe, expect, it } from "vitest";

import {
  appendCin7Files,
  barcodesCsvPath,
  canSeeCin7Import,
  commitBlockedReason,
  errorsCsvPath,
  fileSelectionKey,
  generatedBarcodeHeadline,
  importHeadlines,
  isActiveRun,
  warningsCsvPath,
  type Cin7RunSnapshot,
} from "./cin7-import";

const clean: Cin7RunSnapshot = {
  mode: "dry_run",
  status: "completed",
  error_count: 0,
  file_sha256: "abc",
};

describe("cin7 import page states", () => {
  it("hides the page from roles without users.manage", () => {
    expect(canSeeCin7Import(undefined)).toBe(false);
    expect(canSeeCin7Import(["catalogue.mutate"])).toBe(false);
    expect(canSeeCin7Import(["settings.mutate"])).toBe(false);
    expect(canSeeCin7Import(["users.manage"])).toBe(true);
  });

  it("keeps commit disabled until a clean dry run of the same file", () => {
    const key = fileSelectionKey([{ name: "export.zip", size: 10, lastModified: 1 }]);
    expect(commitBlockedReason(null, key, "")).toBe("Run a dry run first");
    expect(commitBlockedReason(clean, key, "other")).toBe(
      "The selected file does not match the dry run",
    );
    expect(commitBlockedReason({ ...clean, status: "running" }, key, key)).toBe(
      "Dry run is still running",
    );
    expect(commitBlockedReason({ ...clean, status: "queued" }, key, key)).toBe(
      "Dry run is still running",
    );
    expect(commitBlockedReason({ ...clean, status: "failed", error_count: 2 }, key, key)).toBe(
      "Dry run had errors",
    );
    expect(commitBlockedReason({ ...clean, error_count: 1 }, key, key)).toBe("Dry run had errors");
    expect(commitBlockedReason({ ...clean, mode: "commit" }, key, key)).toBe(
      "Commit a dry run, not another commit",
    );
    expect(commitBlockedReason(clean, key, key)).toBeNull();
  });

  it("treats queued and running as in progress", () => {
    expect(isActiveRun("queued")).toBe(true);
    expect(isActiveRun("running")).toBe(true);
    expect(isActiveRun("completed")).toBe(false);
    expect(isActiveRun("failed")).toBe(false);
  });

  it("points downloads at the run csv endpoints", () => {
    expect(warningsCsvPath("run-1")).toBe("/api/v1/cin7-imports/run-1/warnings.csv");
    expect(errorsCsvPath("run-1")).toBe("/api/v1/cin7-imports/run-1/errors.csv");
    expect(barcodesCsvPath("run-1")).toBe("/api/v1/cin7-imports/run-1/barcodes.csv");
  });

  it("shows the dry-run headlines and the generated barcode split", () => {
    const counts = {
      created: 0,
      updated: 0,
      unchanged: 0,
      skipped: 0,
    };
    const headlines = importHeadlines({
      entities: {
        sku: { ...counts, updated: 4964 },
        customer: { ...counts, updated: 218 },
        price_list: { ...counts, created: 4 },
        price_list_item: { ...counts, created: 18978 },
      },
      generated_barcodes: 3925,
      generated_barcodes_blank: 2100,
      generated_barcodes_shared: 1825,
    });
    expect(headlines).toMatchObject({
      skusUpdated: 4964,
      customersUpdated: 218,
      priceListsCreated: 4,
      priceListItemsCreated: 18978,
      generatedBarcodes: 3925,
      generatedBarcodesBlank: 2100,
      generatedBarcodesShared: 1825,
    });
    expect(generatedBarcodeHeadline(3925, 2100, 1825)).toBe(
      "3,925 SKUs would get a generated barcode (2,100 blank, 1,825 shared)",
    );
  });

  it("sends a zip as file and a folder as files", () => {
    const zip = new File(["zip"], "export.zip");
    const zipBody = new FormData();
    appendCin7Files(zipBody, [zip]);
    expect(zipBody.get("file")).toBe(zip);
    expect(zipBody.getAll("files")).toEqual([]);

    const inventory = new File(["a"], "InventoryList.csv");
    const prices = new File(["b"], "SimplePrices.csv");
    const folder = new FormData();
    appendCin7Files(folder, [inventory, prices]);
    expect(folder.get("file")).toBeNull();
    expect(folder.getAll("files")).toEqual([inventory, prices]);
  });
});
