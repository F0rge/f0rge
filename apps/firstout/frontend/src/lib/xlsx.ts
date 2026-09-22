import type { CanvasExportCell, CanvasExportSheet } from "./nia-canvas-export";

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let index = 0; index < 256; index += 1) {
    let crc = index;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = crc & 1 ? 0xedb88320 ^ (crc >>> 1) : crc >>> 1;
    }
    table[index] = crc >>> 0;
  }
  return table;
})();

function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (let index = 0; index < data.length; index += 1) {
    crc = (crc >>> 8) ^ CRC_TABLE[(crc ^ data[index]) & 0xff];
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function encodeUtf8(value: string): Uint8Array {
  return new TextEncoder().encode(value);
}

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("\t", "&#9;")
    .replaceAll("\n", "&#10;");
}

function columnLetters(index: number): string {
  let column = index + 1;
  let letters = "";
  while (column > 0) {
    const remainder = (column - 1) % 26;
    letters = String.fromCharCode(65 + remainder) + letters;
    column = Math.floor((column - 1) / 26);
  }
  return letters;
}

function cellReference(columnIndex: number, rowIndex: number): string {
  return `${columnLetters(columnIndex)}${rowIndex + 1}`;
}

function sanitizeStringCell(value: string): string {
  if (/^[=+\-@]/.test(value)) {
    return `\t${value}`;
  }
  return value;
}

function renderInlineStringCell(ref: string, value: string): string {
  const safe = escapeXml(sanitizeStringCell(value));
  return `<c r="${ref}" t="inlineStr"><is><t>${safe}</t></is></c>`;
}

function renderNumberCell(ref: string, value: number): string {
  return `<c r="${ref}"><v>${value}</v></c>`;
}

function renderCell(ref: string, value: CanvasExportCell): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return renderNumberCell(ref, value);
  }
  return renderInlineStringCell(ref, String(value));
}

function buildWorksheetXml(sheet: CanvasExportSheet): string {
  const rows: string[] = [];
  const headerRow = sheet.headers
    .map((header, columnIndex) => renderInlineStringCell(cellReference(columnIndex, 0), header))
    .join("");
  rows.push(`<row r="1">${headerRow}</row>`);

  sheet.rows.forEach((row, rowIndex) => {
    const cells = row
      .map((cell, columnIndex) => renderCell(cellReference(columnIndex, rowIndex + 1), cell))
      .join("");
    rows.push(`<row r="${rowIndex + 2}">${cells}</row>`);
  });

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    ${rows.join("\n    ")}
  </sheetData>
</worksheet>`;
}

function buildContentTypesXml(sheetCount: number): string {
  const overrides = Array.from({ length: sheetCount }, (_, index) => {
    const part = `/xl/worksheets/sheet${index + 1}.xml`;
    return `<Override PartName="${part}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`;
  }).join("\n  ");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  ${overrides}
</Types>`;
}

function buildRootRelsXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`;
}

function buildWorkbookXml(sheets: CanvasExportSheet[]): string {
  const sheetTags = sheets
    .map((sheet, index) => {
      const name = escapeXml(sheet.name);
      return `<sheet name="${name}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`;
    })
    .join("\n    ");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    ${sheetTags}
  </sheets>
</workbook>`;
}

function buildWorkbookRelsXml(sheetCount: number): string {
  const relationships = Array.from({ length: sheetCount }, (_, index) => {
    return `<Relationship Id="rId${index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${index + 1}.xml"/>`;
  }).join("\n  ");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  ${relationships}
</Relationships>`;
}

type ZipEntry = {
  path: string;
  data: Uint8Array;
};

function buildZipStore(entries: ZipEntry[]): Uint8Array {
  const localParts: Uint8Array[] = [];
  const centralParts: Uint8Array[] = [];
  let offset = 0;

  for (const entry of entries) {
    const nameBytes = encodeUtf8(entry.path);
    const crc = crc32(entry.data);
    const size = entry.data.length;

    const localHeader = new Uint8Array(30 + nameBytes.length);
    const localView = new DataView(localHeader.buffer);
    localView.setUint32(0, 0x04034b50, true);
    localView.setUint16(4, 20, true);
    localView.setUint16(6, 0, true);
    localView.setUint16(8, 0, true);
    localView.setUint16(10, 0, true);
    localView.setUint16(12, 0, true);
    localView.setUint32(14, crc, true);
    localView.setUint32(18, size, true);
    localView.setUint32(22, size, true);
    localView.setUint16(26, nameBytes.length, true);
    localView.setUint16(28, 0, true);
    localHeader.set(nameBytes, 30);

    localParts.push(localHeader, entry.data);

    const centralHeader = new Uint8Array(46 + nameBytes.length);
    const centralView = new DataView(centralHeader.buffer);
    centralView.setUint32(0, 0x02014b50, true);
    centralView.setUint16(4, 20, true);
    centralView.setUint16(6, 20, true);
    centralView.setUint16(8, 0, true);
    centralView.setUint16(10, 0, true);
    centralView.setUint32(16, crc, true);
    centralView.setUint32(20, size, true);
    centralView.setUint32(24, size, true);
    centralView.setUint16(28, nameBytes.length, true);
    centralView.setUint16(30, 0, true);
    centralView.setUint16(32, 0, true);
    centralView.setUint16(34, 0, true);
    centralView.setUint16(36, 0, true);
    centralView.setUint32(38, 0, true);
    centralView.setUint32(42, offset, true);
    centralHeader.set(nameBytes, 46);
    centralParts.push(centralHeader);

    offset += localHeader.length + entry.data.length;
  }

  const centralDirectorySize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const centralDirectoryOffset = offset;

  const endRecord = new Uint8Array(22);
  const endView = new DataView(endRecord.buffer);
  endView.setUint32(0, 0x06054b50, true);
  endView.setUint16(4, 0, true);
  endView.setUint16(6, 0, true);
  endView.setUint16(8, entries.length, true);
  endView.setUint16(10, entries.length, true);
  endView.setUint32(12, centralDirectorySize, true);
  endView.setUint32(16, centralDirectoryOffset, true);
  endView.setUint16(20, 0, true);

  const totalLength =
    localParts.reduce((sum, part) => sum + part.length, 0) + centralDirectorySize + endRecord.length;
  const output = new Uint8Array(totalLength);
  let writeOffset = 0;
  for (const part of [...localParts, ...centralParts, endRecord]) {
    output.set(part, writeOffset);
    writeOffset += part.length;
  }
  return output;
}

export function buildXlsx(sheets: CanvasExportSheet[]): Uint8Array {
  const worksheetEntries = sheets.map((sheet, index) => ({
    path: `xl/worksheets/sheet${index + 1}.xml`,
    data: encodeUtf8(buildWorksheetXml(sheet)),
  }));

  const entries: ZipEntry[] = [
    { path: "[Content_Types].xml", data: encodeUtf8(buildContentTypesXml(sheets.length)) },
    { path: "_rels/.rels", data: encodeUtf8(buildRootRelsXml()) },
    { path: "xl/workbook.xml", data: encodeUtf8(buildWorkbookXml(sheets)) },
    { path: "xl/_rels/workbook.xml.rels", data: encodeUtf8(buildWorkbookRelsXml(sheets.length)) },
    ...worksheetEntries,
  ];

  return buildZipStore(entries);
}

export function downloadXlsx(filename: string, sheets: CanvasExportSheet[]): void {
  if (sheets.length === 0) {
    return;
  }
  const bytes = buildXlsx(sheets);
  const blob = new Blob([Uint8Array.from(bytes)], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
