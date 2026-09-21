import { describe, expect, it } from "vitest";

import type { CanvasExportSheet } from "./nia-canvas-export";
import { buildXlsx } from "./xlsx";

function readStoreZipEntry(data: Uint8Array, entryPath: string): string | null {
  const nameBytes = new TextEncoder().encode(entryPath);
  let offset = 0;

  while (offset + 30 <= data.length) {
    const view = new DataView(data.buffer, data.byteOffset + offset, 30);
    if (view.getUint32(0, true) !== 0x04034b50) {
      break;
    }
    const compression = view.getUint16(8, true);
    const compressedSize = view.getUint32(18, true);
    const nameLength = view.getUint16(26, true);
    const extraLength = view.getUint16(28, true);
    const nameStart = offset + 30;
    const entryName = data.slice(nameStart, nameStart + nameLength);
    const payloadStart = nameStart + nameLength + extraLength;
    if (
      compression === 0 &&
      entryName.length === nameBytes.length &&
      entryName.every((byte, index) => byte === nameBytes[index])
    ) {
      return new TextDecoder().decode(
        data.slice(payloadStart, payloadStart + compressedSize),
      );
    }
    offset = payloadStart + compressedSize;
  }

  return null;
}

describe("buildXlsx", () => {
  const sampleSheets: CanvasExportSheet[] = [
    {
      name: "Stock",
      headers: ["SKU", "Location"],
      rows: [
        ["VEL-SOFA-LONDON", "Kramerville"],
        ["=1+1", "Dining"],
        ["PG-TABLE", 1],
      ],
    },
  ];

  it("writes a ZIP archive with worksheet XML", () => {
    const bytes = buildXlsx(sampleSheets);
    expect(bytes[0]).toBe(0x50);
    expect(bytes[1]).toBe(0x4b);

    const worksheet = readStoreZipEntry(bytes, "xl/worksheets/sheet1.xml");
    expect(worksheet).toBeDefined();
    expect(worksheet).toContain("VEL-SOFA-LONDON");
    expect(worksheet).toContain("Dining");
    expect(worksheet).toContain("<t>&#9;=1+1</t>");
    expect(worksheet).toMatch(/<v>1<\/v>/);
  });
});
