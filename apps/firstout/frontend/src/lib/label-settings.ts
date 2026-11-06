import { getSettings } from "./api";
import { staffFetch } from "./staff-fetch";

export type LabelSettings = {
  label_width_mm: number;
  label_height_mm: number;
  label_show_name: boolean;
  label_show_reference: boolean;
  label_show_barcode: boolean;
  label_show_logo: boolean;
};
/** Fetch on every print; settings and logo must never be cached across tenants. */
export async function loadLabelSettings() {
  const settings = await getSettings();
  let logo = "";
  if (settings.label_show_logo && settings.has_logo) {
    const response = await staffFetch("/api/v1/settings/logo");
    if (!response.ok)
      throw new Error("Unable to load your organisation’s logo.");
    const blob = await response.blob();
    if (!["image/png", "image/jpeg", "image/webp"].includes(blob.type))
      throw new Error("Unsupported label logo.");
    logo = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }
  return { ...settings, logo };
}
export function labelPageCss(settings: LabelSettings): string {
  // Guard CSS interpolation even if a response is malformed.
  const width = Math.max(
    20,
    Math.min(300, Number(settings.label_width_mm) || 100),
  );
  const height = Math.max(
    20,
    Math.min(300, Number(settings.label_height_mm) || 60),
  );
  return `@page { size: ${width}mm ${height}mm; margin: 0; } .label { box-sizing: border-box; width: ${width}mm; min-height: ${height}mm; } .label-logo { max-width: 30mm; max-height: 15mm; }`;
}
