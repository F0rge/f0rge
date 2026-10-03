import { deliveryZoneForAddress, deliveryZones } from "./delivery-zones";

describe("server delivery zones", () => {
  const config = JSON.stringify([{
    id: "joburg-test", name: "Johannesburg test zone", cities: ["Johannesburg"],
    suburbs: ["Rosebank"], postal_codes: ["2196"], rate_zar: 85.5,
  }]);

  test("validates cent-accurate rates and matches configured city, suburb, postal code, and province", () => {
    const zones = deliveryZones(config);
    expect(deliveryZoneForAddress({ province: "Gauteng", city: " Johannesburg ", address_2: "Rosebank", postal_code: "2196" }, zones)?.rate_zar).toBe(85.5);
    expect(deliveryZoneForAddress({ province: "Western Cape", city: "Johannesburg", address_2: "Rosebank", postal_code: "2196" }, zones)).toBeNull();
    expect(deliveryZoneForAddress({ province: "Gauteng", city: "Johannesburg", address_2: "Sandton", postal_code: "2196" }, zones)).toBeNull();
    expect(deliveryZoneForAddress({ province: "Gauteng", city: "Johannesburg", address_2: "Rosebank", postal_code: "2197" }, zones)).toBeNull();
  });

  test("fails closed on missing coverage, invalid JSON, duplicate IDs, and fractional cents", () => {
    expect(deliveryZones()).toEqual([]);
    expect(() => deliveryZones("{" )).toThrow(/valid JSON/i);
    expect(() => deliveryZones(JSON.stringify([
      { id: "same", name: "A", cities: ["A"], rate_zar: 1 },
      { id: "same", name: "B", cities: ["B"], rate_zar: 1 },
    ]))).toThrow(/invalid/i);
    expect(() => deliveryZones(JSON.stringify([{ id: "zone", name: "Zone", cities: ["A"], rate_zar: 1.001 }]))).toThrow(/invalid/i);
  });
});
