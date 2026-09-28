import { MedusaError } from "@medusajs/framework/utils";

export type DeliveryZone = {
  id: string;
  name: string;
  cities: string[];
  suburbs: string[];
  postal_codes: string[];
  rate_zar: number;
};

type Address = { city?: string | null; province?: string | null; postal_code?: string | null; address_2?: string | null };

function normalized(value: unknown): string {
  return typeof value === "string" ? value.trim().toLocaleLowerCase("en-ZA") : "";
}

export function deliveryZones(source = process.env.STOREFRONT_GAUTENG_DELIVERY_ZONES): DeliveryZone[] {
  if (!source) return [];
  let parsed: unknown;
  try { parsed = JSON.parse(source); }
  catch { throw new MedusaError(MedusaError.Types.INVALID_DATA, "STOREFRONT_GAUTENG_DELIVERY_ZONES must be valid JSON"); }
  if (!Array.isArray(parsed)) throw new MedusaError(MedusaError.Types.INVALID_DATA, "Delivery zones must be a JSON array");
  const ids = new Set<string>();
  return parsed.map((value): DeliveryZone => {
    if (!value || typeof value !== "object") throw new MedusaError(MedusaError.Types.INVALID_DATA, "Each delivery zone must be an object");
    const zone = value as Partial<DeliveryZone>;
    if (typeof zone.id !== "string" || !/^[a-z0-9][a-z0-9_-]{0,39}$/.test(zone.id) || ids.has(zone.id) ||
      typeof zone.name !== "string" || !zone.name.trim() ||
      !Array.isArray(zone.cities) || zone.cities.length === 0 || !zone.cities.every((entry) => typeof entry === "string" && entry.trim()) ||
      (zone.suburbs !== undefined && (!Array.isArray(zone.suburbs) || !zone.suburbs.every((entry) => typeof entry === "string" && entry.trim()))) ||
      (zone.postal_codes !== undefined && (!Array.isArray(zone.postal_codes) || !zone.postal_codes.every((entry) => typeof entry === "string" && /^\d{4}$/.test(entry)))) ||
      typeof zone.rate_zar !== "number" || !Number.isFinite(zone.rate_zar) || zone.rate_zar < 0 || Math.round(zone.rate_zar * 100) !== zone.rate_zar * 100) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "A delivery zone has invalid identifiers, coverage, or a non-cent ZAR rate");
    }
    ids.add(zone.id);
    return {
      id: zone.id,
      name: zone.name.trim(),
      cities: zone.cities.map((entry) => entry.trim()),
      suburbs: (zone.suburbs || []).map((entry) => entry.trim()),
      postal_codes: zone.postal_codes || [],
      rate_zar: zone.rate_zar,
    };
  });
}

export function deliveryZoneForAddress(address: Address, zones = deliveryZones()): DeliveryZone | null {
  if (normalized(address.province) !== "gauteng") return null;
  const city = normalized(address.city);
  const suburb = normalized(address.address_2);
  const postalCode = typeof address.postal_code === "string" ? address.postal_code.trim() : "";
  return zones.find((zone) =>
    zone.cities.some((candidate) => normalized(candidate) === city) &&
    (!zone.suburbs.length || zone.suburbs.some((candidate) => normalized(candidate) === suburb)) &&
    (!zone.postal_codes.length || zone.postal_codes.includes(postalCode))) || null;
}
