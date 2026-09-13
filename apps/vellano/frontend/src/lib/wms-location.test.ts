import { describe, expect, it } from "vitest";

import type { Location } from "@/lib/api";
import {
  defaultFloorLocationId,
  floorLocations,
  resolveFloorLocationId,
} from "@/lib/wms-location";

function loc(
  id: string,
  name: string,
  type: Location["type"],
  is_archived = false,
): Location {
  return {
    id,
    name,
    type,
    is_archived,
    archived_at: is_archived ? "2026-02-01T00:00:00Z" : null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

const warehouse = loc("loc-k", "Kramerville", "warehouse");
const showroom = loc("loc-b", "Bedfordview", "showroom");
const third = loc("loc-p", "Pretoria", "showroom");

describe("wms-location", () => {
  it("lists every active location, including a third site", () => {
    const floor = floorLocations([warehouse, showroom, third]);
    expect(floor.map((location) => location.id)).toEqual(["loc-k", "loc-b", "loc-p"]);
  });

  it("omits archived locations and still works after a rename", () => {
    const renamed = loc("loc-k", "JHB Warehouse", "warehouse");
    const archived = loc("loc-b", "Bedfordview", "showroom", true);
    const floor = floorLocations([renamed, archived, third]);
    expect(floor.map((location) => location.id)).toEqual(["loc-k", "loc-p"]);
  });

  it("defaults to the first warehouse when nothing is stored", () => {
    const floor = floorLocations([showroom, warehouse, third]);
    expect(defaultFloorLocationId(floor)).toBe("loc-k");
    expect(resolveFloorLocationId(floor, null)).toBe("loc-k");
  });

  it("restores a stored third-location selection", () => {
    const floor = floorLocations([warehouse, showroom, third]);
    expect(resolveFloorLocationId(floor, "loc-p")).toBe("loc-p");
  });

  it("falls back when the stored id is no longer active", () => {
    const floor = floorLocations([warehouse, third]);
    expect(resolveFloorLocationId(floor, "loc-b")).toBe("loc-k");
  });
});
