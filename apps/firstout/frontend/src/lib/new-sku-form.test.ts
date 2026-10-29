import { describe, expect, it } from "vitest";

import {
  missingNewSkuFields,
  missingNewSkuMessage,
  pickSkuPhoto,
  type NewSkuFieldInput,
} from "./new-sku-form";

const ready: NewSkuFieldInput = {
  ourRef: "DC-23-11G",
  name: "Moseli Dining Chair 58*54*79 cm",
  design: "Dining Chair",
  fabric: "Teddy - C01",
  cartonCount: 1,
  recordStockNow: false,
  openingLocationId: "",
  openingQty: 1,
  openingUnitCost: "",
};

describe("missingNewSkuFields", () => {
  it("lets a SKU save with the barcode left blank", () => {
    expect(missingNewSkuFields(ready)).toEqual([]);
    expect(missingNewSkuMessage([])).toBeNull();
  });

  it("names every required field that is still empty", () => {
    const missing = missingNewSkuFields({
      ...ready,
      ourRef: "  ",
      name: "",
      cartonCount: "",
    });
    expect(missing).toEqual(["Our ref", "Name", "Cartons"]);
    expect(missingNewSkuMessage(missing)).toBe(
      "Our ref, Name, and Cartons are required before you can save.",
    );
  });

  it("names a single missing field", () => {
    expect(missingNewSkuMessage(missingNewSkuFields({ ...ready, fabric: "" }))).toBe(
      "Fabric is required before you can save.",
    );
  });

  it("names opening-stock fields only when stock is being recorded", () => {
    expect(
      missingNewSkuFields({
        ...ready,
        recordStockNow: true,
        openingLocationId: "",
        openingQty: "",
        openingUnitCost: "0",
      }),
    ).toEqual(["Location", "Quantity on hand", "Unit cost"]);
  });
});

describe("pickSkuPhoto", () => {
  it("keeps a PNG whose name has spaces when Carbon returns no added files", () => {
    const file = new File([Uint8Array.from([137, 80, 78, 71])], "1602DC-23-11G dining chair.png", {
      type: "image/png",
    });
    const picked = pickSkuPhoto({ target: { files: [file] } }, []);
    expect(picked.error).toBeNull();
    expect(picked.file).toBe(file);
  });

  it("keeps that PNG when Carbon flags image/* as an invalid type", () => {
    const file = new File([Uint8Array.from([137, 80, 78, 71])], "1602DC-23-11G dining chair.png", {
      type: "image/png",
    });
    Object.assign(file, { invalidFileType: true });
    const picked = pickSkuPhoto(null, [file]);
    expect(picked.error).toBeNull();
    expect(picked.file?.name).toBe("1602DC-23-11G dining chair.png");
  });

  it("reads a dropped file from the drag event", () => {
    const file = new File([Uint8Array.from([1])], "chair.png", { type: "image/png" });
    const picked = pickSkuPhoto({ dataTransfer: { files: [file] } }, []);
    expect(picked.file).toBe(file);
    expect(picked.error).toBeNull();
  });

  it("accepts an image extension when the browser leaves the MIME type empty", () => {
    const file = new File([Uint8Array.from([1])], "1602DC-23-11G dining chair.png", { type: "" });
    const picked = pickSkuPhoto({ target: { files: [file] } }, []);
    expect(picked.file).toBe(file);
  });

  it("explains a file that is not an image", () => {
    const file = new File(["hello"], "1602DC-23-11G dining chair.txt", { type: "text/plain" });
    const picked = pickSkuPhoto({ target: { files: [file] } }, []);
    expect(picked.file).toBeNull();
    expect(picked.error).toBe(
      `"1602DC-23-11G dining chair.txt" isn't a supported image. Use a JPEG, PNG, or WebP file.`,
    );
  });

  it("explains an empty selection", () => {
    expect(pickSkuPhoto({ target: { files: [] } }, []).error).toMatch(/No image was added/);
  });
});
