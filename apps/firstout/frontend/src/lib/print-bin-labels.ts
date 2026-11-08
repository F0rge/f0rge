import { loadLabelSettings, labelPageCss } from "./label-settings";
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

export async function printBinLabels(bins: LocationBin[]): Promise<void> {
  if (bins.every((bin) => bin.is_archived)) return;
  const printWindow = window.open("", "_blank");
  if (!printWindow) {
    window.alert("Allow pop-ups to print.");
    return;
  }
  try {
    const settings = await loadLabelSettings();
    const active = bins.filter((bin) => !bin.is_archived);
    if (active.length === 0) {
      return;
    }
    const labelsHtml = active
      .map(
        (bin) => `
    <div class="label">
      ${settings.logo ? `<img class="label-logo" src="${settings.logo}" alt="" />` : ""}
      ${settings.label_show_reference ? `<div class="code">${escapeHtml(bin.code)}</div>` : ""}
      ${settings.label_show_name ? `<div class="meta">Row ${escapeHtml(bin.row_code)} · Bay ${bin.bay} · Level ${bin.level}</div>` : ""}
      ${settings.label_show_barcode ? barcodeMarkup(bin.code) : ""}
    </div>`,
      )
      .join("");
    printHtml(
      `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Bin labels</title>
  <style>
    ${labelPageCss(settings)}
    body { font-family: "IBM Plex Sans", sans-serif; margin: 1.5rem; color: #161616; }
    .label { page-break-inside: avoid; margin-bottom: 2rem; padding: 1rem; border: 1px solid #e0e0e0; }
    .code { font-family: "IBM Plex Mono", monospace; font-size: 1.25rem; font-weight: 600; margin-bottom: 0.25rem; }
    .meta { color: #525252; font-size: 0.875rem; margin-bottom: 0.75rem; }
    @media print { body { margin: 0; } .label { border: none; } }
  </style>
</head>
<body>${labelsHtml}</body>
</html>`,
      printWindow,
    );
  } catch (error) {
    printWindow.close();
    window.alert(
      error instanceof Error ? error.message : "Unable to load label settings.",
    );
  }
}
