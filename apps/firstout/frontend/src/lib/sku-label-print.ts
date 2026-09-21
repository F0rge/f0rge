import JsBarcode from "jsbarcode";

import { printHtml } from "@/lib/print-html";
import type { Sku } from "@/lib/api";

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function barcodeSvg(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  try {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    JsBarcode(svg, trimmed, { format: "CODE128", displayValue: true, font: "monospace" });
    return svg.outerHTML;
  } catch {
    return `<div class="barcode-text">${escapeHtml(trimmed)}</div>`;
  }
}

export function printSkuLabels(targetSkus: Sku[]): void {
  if (targetSkus.length === 0) {
    return;
  }
  const labelsHtml = targetSkus
    .map(
      (sku) => `
    <div class="label">
      <div class="name">${escapeHtml(sku.name)}</div>
      <div class="ref">${escapeHtml(sku.our_ref)}</div>
      ${barcodeSvg(sku.our_barcode)}
    </div>`,
    )
    .join("");
  printHtml(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Barcode labels</title>
  <style>
    body { font-family: "IBM Plex Sans", sans-serif; margin: 1.5rem; color: #161616; }
    .label { page-break-inside: avoid; margin-bottom: 2rem; padding: 1rem; border: 1px solid #e0e0e0; }
    .name { font-size: 1rem; margin-bottom: 0.25rem; }
    .ref { font-weight: 600; margin-bottom: 0.5rem; }
    .barcode-text { font-family: monospace; font-size: 1.75rem; font-weight: 600; letter-spacing: 0.05em; }
    svg { display: block; max-width: 100%; height: auto; }
    @media print { body { margin: 0; } .label { border: none; } }
  </style>
</head>
<body>${labelsHtml}</body>
</html>`);
}
