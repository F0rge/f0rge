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
  value: string;
  width: number;
  height?: number;
  label?: string;
  sourceSku?: string;
};

type SampleGroup = Pick<MaterialSample, "kind" | "sourceLabel" | "groupTitle" | "optionNote"> & {
  axis: string;
  crops: Readonly<Record<string, Crop>>;
};

// The Kidman originals share one image. The Swank originals identify these exact Solo fabric codes.
const solo111: Crop = { value: "Solo 111", width: 475, sourceSku: "P20305" };
const solo451: Crop = { value: "Solo 451", width: 285, sourceSku: "P20306" };
const soloSource = "Solo fabrics photographed on the Swank chair.";

// Crops come from the source SKU's original Firstout catalogue photograph, before studio processing.
// Width and height describe the native crop. Small colour and finish samples use it for both views.
const groups: readonly SampleGroup[] = [
  {
    axis: "Upholstery",
    kind: "material",
    sourceLabel: "Upholstery photographed on the Francoise armchairs.",
    crops: {
      P20260: { value: "Grey / A0605200", width: 245 },
      P20261: { value: "Starry / A0605211", width: 245 },
    },
  },
  {
    axis: "Upholstery",
    kind: "material",
    sourceLabel: "Upholstery photographed on the Segolene armchairs.",
    crops: {
      P20262: { value: "U777023 / split leather", width: 140 },
      P20265: { value: "A0302910", width: 135 },
    },
  },
  {
    axis: "Upholstery",
    kind: "material",
    sourceLabel: "Upholstery photographed on the Solange armchairs.",
    crops: {
      P20263: { value: "G0602120", width: 230 },
      P20264: { value: "Dove / A0303020", width: 280 },
    },
  },
  {
    axis: "Upholstery",
    kind: "colour",
    sourceLabel: "Colour samples from the original Winslet chair photographs.",
    crops: {
      P20303: { value: "Milan 104", width: 230 },
      P20304: { value: "Ote Lisa 453", width: 53 },
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
      P36409: { value: "Rose gold frame", width: 68 },
      P36410: { value: "Grey / silver-tone frame", width: 68 },
    },
  },
  {
    axis: "Metal finish",
    kind: "finish",
    sourceLabel: "Metal frames from the original Kinita table photographs.",
    crops: {
      P61349: { value: "Silver", width: 42 },
      P61350: { value: "Gold", width: 60 },
    },
  },
  {
    axis: "Upholstery",
    kind: "colour",
    groupTitle: "Upholstery colour",
    optionNote: "Silver frame on every colour.",
    sourceLabel: "Colour samples from the original Alexa chair photographs.",
    crops: {
      P62131X2: { value: "Grey / silver frame", label: "Grey", width: 66, height: 70 },
      P62132X2: { value: "White PU / silver frame", label: "White PU", width: 60, height: 66 },
      P62129X2: { value: "Navy velvet / silver frame", label: "Navy velvet", width: 70, height: 69 },
    },
  },
  {
    axis: "Upholstery material",
    kind: "material",
    sourceLabel: "Upholstery photographed on the Biles chairs.",
    crops: {
      P62673: { value: "Grey PU", width: 280 },
      P62674: { value: "Grey fabric / AS1687-9", width: 280 },
    },
  },
  {
    axis: "Upholstery colour",
    kind: "colour",
    sourceLabel: "Headboard upholstery from the original Simone bed photographs.",
    crops: {
      P62687PC4: { value: "Grey / JES-564-16", width: 95 },
      P62686PC4: { value: "Gold / JES-564-42", width: 95 },
    },
  },
];

/** Match the current option as well as the SKU so changed catalogue values fall back to their own labels. */
export function materialSample(
  sku: string | null | undefined,
  optionTitle: string,
  optionValue: string,
): MaterialSample | undefined {
  if (!sku) return undefined;
  const group = groups.find(({ axis, crops }) => axis === optionTitle && Object.hasOwn(crops, sku));
  const crop = group?.crops[sku];
  if (!group || !crop || crop.value !== optionValue) return undefined;

  const prefix = `/swatches/${(crop.sourceSku ?? sku).toLowerCase()}`;
  const detail = `${prefix}.webp`;
  const height = crop.height ?? crop.width;
  return {
    kind: group.kind,
    label: crop.label ?? crop.value,
    swatch: Math.max(crop.width, height) > 144 ? `${prefix}-thumb.webp` : detail,
    detail,
    width: crop.width,
    height,
    sourceLabel: group.sourceLabel,
    groupTitle: group.groupTitle,
    optionNote: group.optionNote,
  };
}
