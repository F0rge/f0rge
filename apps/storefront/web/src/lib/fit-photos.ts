export type FitPhoto = {
  url: string;
  size: readonly [width: number, height: number];
  bounds: readonly [left: number, top: number, right: number, bottom: number];
  rim?: { cx: number; cy: number; rx: number; ry: number };
};

type Calibration = readonly [file: string, size: FitPhoto["size"], bounds: FitPhoto["bounds"], rim?: FitPhoto["rim"]];

// Bounds enclose the furniture in the reference raster, excluding its shadow.
// Rim coordinates follow the outer edge of the tabletop, in that same pixel space.
const studioUploads = "https://medusa.firstout.co.za/static/";
const calibrations: Readonly<Record<string, Calibration>> = {
  P20301PC3: ["1795356257317-firstout-c8d4e8d0-fbab-41fc-aea3-f2532ab4a7e3-2.jpg", [300, 146], [6, 38, 293, 114]],
  P20302PC3: ["1795673405311-firstout-e9d05533-69a5-44fd-b5af-5c6739c73f5f-1.jpg", [860, 367], [22, 84, 841, 288]],
  P20303: ["1795356275521-firstout-af7cc2a2-dbba-417b-9c07-8c3a152ca635-1.jpg", [540, 540], [18, 36, 521, 501]],
  P20304: ["1795356275917-firstout-5d5a29f4-4ee2-475a-8fb1-13e1791af209-1.jpg", [540, 540], [16, 33, 521, 496]],
  P20305: ["1795356276288-firstout-88680efe-1ee3-43fc-b3ea-fb2a34f2d129-1.jpg", [540, 540], [10, 18, 529, 504]],
  P20306: ["1795356276608-firstout-529ea062-296d-4bec-88ab-f9745c308c5f-1.jpg", [540, 540], [10, 17, 529, 503]],
  P20307PC3: ["1795673406123-firstout-d493e5ef-11c4-43c2-aa04-ef0e735a6264-1.jpg", [860, 359], [21, 88, 845, 288]],
  P20318: ["1795356258940-firstout-d6343a1f-80eb-491e-9443-d361905c097c-2.jpg", [300, 213], [57, 16, 244, 198]],
  P35043PC2: ["1795356259513-firstout-f2862f06-6712-4f6a-8098-9baec5e4361b-2.jpg", [300, 153], [14, 36, 284, 127]],
  P36441: ["1795356260843-firstout-56af39b1-c2d5-448f-bfe6-dc227794dfc7-2.jpg", [300, 200], [72, 16, 228, 181]],
  P36453: ["1795364584961-firstout-28bb3428-f153-412d-8aa6-494d3530a3c5-1.jpg", [540, 540], [34, 221, 506, 381]],
  P60615: ["1795356261264-firstout-9e9cb0e8-f44a-42d1-ae03-7e18b96122c6-2.jpg", [300, 200], [24, 31, 275, 166]],
  P60857: ["1795356262126-firstout-321d5a1e-f495-4f30-977e-8a19a1865a2b-1.jpg", [540, 540], [24, 159, 511, 439]],
  P61347: ["1795356262949-firstout-14eae46a-1beb-4c4f-ac03-a9acca3fda27-1.jpg", [540, 360], [64, 55, 477, 334]],
  P61349: ["1795356278011-firstout-fd998505-e105-443a-845f-ae0e49cf2fdf-1.jpg", [540, 360], [58, 88, 483, 316]],
  P61350: ["1795356278341-firstout-ed7d04b5-0569-4759-afd2-b9671ddb7f87-1.jpg", [540, 360], [58, 88, 484, 316]],
  P61399: ["1795356263375-firstout-b1ed80f4-2351-40f6-afdc-df30e3f6ce7a-1.jpg", [540, 270], [11, 45, 527, 239]],
  P61425: ["1795356263808-firstout-ee28d77e-7bce-4cb1-b0a2-efb68a1bc955-2.jpg", [300, 200], [23, 36, 278, 169]],
  P61546PC2: ["1795356264771-firstout-6129a8d1-7321-4a6c-93e5-ce369e768d87-1.jpg", [540, 360], [70, 83, 446, 298], { cx: 257.5, cy: 133, rx: 187.5, ry: 49.5 }],
  P61551PC2: ["1795356265398-firstout-94faa023-1a77-4d5e-b684-1c9de612577b-1.jpg", [540, 540], [81, 160, 457, 438], { cx: 264.5, cy: 207.5, rx: 180.5, ry: 41 }],
  P61601: ["1795356265927-firstout-3ae5238e-4882-4ca2-8817-fcfc6fe18afc-1.jpg", [540, 540], [17, 101, 521, 439], { cx: 269, cy: 140, rx: 251.5, ry: 39.2 }],
  P61602: ["1795356266371-firstout-a32f7a15-f21b-492c-bfd7-405d9e3eec1e-1.jpg", [540, 200], [21, 26, 517, 175]],
  P62129X2: ["1795356278633-firstout-5e80cee6-3241-4e54-9e25-176e1f968abe-1.jpg", [540, 578], [159, 80, 389, 532]],
  P62131X2: ["1795356279004-firstout-9a240afe-0c94-4213-92c5-23c32a57488d-1.jpg", [540, 579], [161, 82, 389, 531]],
  P62132X2: ["1795356279306-firstout-e3253e8a-60bb-4146-9732-077bebf162ae-1.jpg", [540, 579], [158, 79, 389, 533]],
  P62142: ["1795356267584-firstout-5b556570-87f2-4c66-878f-6981521cd521-2.jpg", [300, 216], [58, 37, 241, 188]],
  P62655: ["1795356268886-firstout-b2f77cca-cd18-4bb8-a707-8798d6681356-2.jpg", [300, 300], [63, 18, 226, 270]],
  P62663: ["1795356269350-firstout-c8744ffc-d47e-47c2-9cfb-b2f1011bf629-2.jpg", [300, 329], [35, 7, 265, 315]],
  P62666: ["1795356269928-firstout-76a88813-1a9e-4b28-88f2-381c67b69436-2.jpg", [300, 300], [16, 10, 283, 287]],
  P62668X2: ["1795356270410-firstout-e0b625e6-494b-4b0c-96e8-04524f742258-2.jpg", [300, 328], [33, 7, 263, 309]],
  P62670: ["1795356270971-firstout-ffd50e1f-ffe1-44a6-bc72-146281925efb-1.jpg", [540, 540], [85, 99, 441, 453]],
  P62672: ["1795356271475-firstout-e0b198e4-a2f1-4906-aed4-e8519d69dc8f-2.jpg", [300, 274], [22, 25, 279, 251]],
  P62673: ["1795356279576-firstout-b873b9df-4be4-4b77-88e7-9ab9326f4680-2.jpg", [300, 365], [14, 20, 281, 351]],
  P62674: ["1795356279914-firstout-3cebda40-7bd0-4fef-a3ff-11de173f12c6-2.jpg", [300, 366], [12, 17, 283, 350]],
  P62683PC2: ["1795356272614-firstout-853f5295-1d16-4e50-b9af-96116c9e89dd-1.jpg", [540, 493], [11, 61, 525, 443]],
  P62721PC2: ["1795356273099-firstout-00f93cc1-a900-4275-82b1-5797b4c2b470-1.jpg", [540, 193], [15, 20, 528, 173]],
};

/** A changed upload needs its own calibration, even if it occupies the same gallery slot. */
export function fitPhoto(sku: string | null | undefined, gallery: readonly string[]): FitPhoto | undefined {
  if (!sku || !Object.hasOwn(calibrations, sku)) return undefined;
  const [file, size, bounds, rim] = calibrations[sku];
  const url = studioUploads + file;
  if (gallery.includes(url)) return { url, size, bounds, rim };
}
