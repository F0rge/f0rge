export type MaterialSample = {
  kind: "fabric" | "material" | "colour" | "finish";
  label: string;
  swatch: string;
  detail: string;
  width: number;
  height: number;
  sourceLabel: string;
  groupTitle?: string;
  optionNote?: string;
};

type Crop = {
  label: string;
  legacyValue?: string;
  width: number;
  sourceSku?: string;
};

type SampleGroup = Pick<MaterialSample, "kind" | "sourceLabel" | "groupTitle" | "optionNote"> & {
  axis: string;
  crops: Readonly<Record<string, Crop>>;
};

// The Kidman originals share one image. The Swank originals identify these exact Solo fabric codes.
const solo111: Crop = { label: "Sand Fabric", legacyValue: "Solo 111", width: 650, sourceSku: "P20305" };
const solo451: Crop = { label: "Taupe Fabric", legacyValue: "Solo 451", width: 395, sourceSku: "P20306" };
const soloSource = "Solo fabrics photographed on the Swank chair.";

// Crops come from the source SKU's original Firstout catalogue photograph, before studio processing.
// The width describes the native square crop. Small crops use the same asset in both views.
const groups: readonly SampleGroup[] = [
  {
    axis: "Upholstery",
    kind: "material",
    sourceLabel: "Upholstery photographed on the Francoise armchairs.",
    crops: {
      P20260: { label: "Smoke Grey Textured Fabric", legacyValue: "Grey / A0605200", width: 350 },
      P20261: { label: "Warm Taupe Textured Fabric", legacyValue: "Starry / A0605211", width: 350 },
    },
  },
  {
    axis: "Upholstery",
    kind: "material",
    sourceLabel: "Upholstery photographed on the Segolene armchairs.",
    crops: {
      P20262: { label: "Olive Grey Split Leather", legacyValue: "U777023 / split leather", width: 280 },
      P20265: { label: "Pebble Taupe Textured Fabric", legacyValue: "A0302910", width: 272 },
    },
  },
  {
    axis: "Upholstery",
    kind: "material",
    sourceLabel: "Upholstery photographed on the Solange armchairs.",
    crops: {
      P20263: { label: "Espresso Fabric", legacyValue: "G0602120", width: 328 },
      P20264: { label: "Dove Grey Fabric", legacyValue: "Dove / A0303020", width: 345 },
    },
  },
  {
    axis: "Upholstery",
    kind: "colour",
    sourceLabel: "Colour samples from the original Winslet chair photographs.",
    crops: {
      P20303: { label: "Heather Grey Fabric", legacyValue: "Milan 104", width: 510 },
      P20304: { label: "Ivory Fabric", legacyValue: "Ote Lisa 453", width: 101 },
    },
  },
  {
    axis: "Upholstery",
    kind: "fabric",
    sourceLabel: soloSource,
    crops: { P20305: solo111, P20306: solo451 },
  },
  {
    axis: "Upholstery material",
    kind: "fabric",
    sourceLabel: soloSource,
    crops: { P20307PC3: solo111, P20302PC3: solo451 },
  },
  {
    axis: "Frame finish",
    kind: "finish",
    sourceLabel: "Frame corners from the original Eva headboard photographs.",
    crops: {
      P36409: { label: "Rose Gold", legacyValue: "Rose gold frame", width: 144 },
      P36410: { label: "Silver", legacyValue: "Grey / silver-tone frame", width: 143 },
    },
  },
  {
    axis: "Metal finish",
    kind: "finish",
    sourceLabel: "Metal frames from the original Kinita table photographs.",
    crops: {
      P61349: { label: "Silver", width: 154 },
      P61350: { label: "Gold", width: 111 },
    },
  },
  {
    axis: "Upholstery",
    kind: "colour",
    groupTitle: "Upholstery colour",
    optionNote: "Silver frame",
    sourceLabel: "Colour samples from the original Alexa chair photographs.",
    crops: {
      P62131X2: { label: "Light Grey", legacyValue: "Grey / silver frame", width: 121 },
      P62132X2: { label: "White Faux Leather", legacyValue: "White PU / silver frame", width: 119 },
      P62129X2: { label: "Navy Velvet", legacyValue: "Navy velvet / silver frame", width: 138 },
    },
  },
  {
    axis: "Upholstery material",
    kind: "material",
    sourceLabel: "Upholstery photographed on the Biles chairs.",
    crops: {
      P62673: { label: "Grey Faux Leather", legacyValue: "Grey PU", width: 390 },
      P62674: { label: "Grey Textured Fabric", legacyValue: "Grey fabric / AS1687-9", width: 390 },
    },
  },
  {
    axis: "Upholstery colour",
    kind: "colour",
    sourceLabel: "Headboard upholstery from the original Simone bed photographs.",
    crops: {
      P62687PC4: { label: "Graphite Grey", legacyValue: "Grey / JES-564-16", width: 278 },
      P62686PC4: { label: "Antique Gold", legacyValue: "Gold / JES-564-42", width: 245 },
    },
  },
];

/** Accept the exact previous label during catalogue sync. Unreviewed options use their own labels. */
export function materialSample(
  sku: string | null | undefined,
  optionTitle: string,
  optionValue: string,
): MaterialSample | undefined {
  if (!sku) return undefined;
  const group = groups.find(({ axis, crops }) => axis === optionTitle && Object.hasOwn(crops, sku));
  const crop = group?.crops[sku];
  if (!group || !crop || (crop.label !== optionValue && crop.legacyValue !== optionValue)) return undefined;

  const prefix = `/swatches/${(crop.sourceSku ?? sku).toLowerCase()}`;
  const detail = `${prefix}.webp`;
  return {
    kind: group.kind,
    label: crop.label,
    swatch: crop.width > 144 ? `${prefix}-thumb.webp` : detail,
    detail,
    width: crop.width,
    height: crop.width,
    sourceLabel: group.sourceLabel,
    groupTitle: group.groupTitle,
    optionNote: group.optionNote,
  };
}
