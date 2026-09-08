import JsBarcode from "jsbarcode";

import { printHtml } from "@/lib/print-html";
import type { LocationBin } from "@/lib/api";

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function barcodeMarkup(code: string): string {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  try {
    JsBarcode(svg, code, {
      format: "CODE128",
      displayValue: true,
      fontSize: 16,
      height: 48,
      margin: 8,
    });
    return svg.outerHTML;
  } catch {
    return `<div class="code">${escapeHtml(code)}</div>`;
  }
}

export function printBinLabels(bins: LocationBin[]): void {
  const active = bins.filter((bin) => !bin.is_archived);
  if (active.length === 0) {
    return;
  }
  const labelsHtml = active
    .map(
      (bin) => `
    <div class="label">
      <div class="code">${escapeHtml(bin.code)}</div>
      <div class="meta">Row ${escapeHtml(bin.row_code)} · Bay ${bin.bay} · Level ${bin.level}</div>
      ${barcodeMarkup(bin.code)}
    </div>`,
    )
    .join("");
  printHtml(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Bin labels</title>
  <style>
    body { font-family: "IBM Plex Sans", sans-serif; margin: 1.5rem; color: #161616; }
    .label { page-break-inside: avoid; margin-bottom: 2rem; padding: 1rem; border: 1px solid #e0e0e0; }
    .code { font-family: "IBM Plex Mono", monospace; font-size: 1.25rem; font-weight: 600; margin-bottom: 0.25rem; }
    .meta { color: #525252; font-size: 0.875rem; margin-bottom: 0.75rem; }
    @media print { body { margin: 0; } .label { border: none; } }
  </style>
</head>
<body>${labelsHtml}</body>
</html>`);
}
