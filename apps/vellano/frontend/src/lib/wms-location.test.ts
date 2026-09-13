import { describe, expect, it } from "vitest";

import type { Location } from "@/lib/api";
import {
  defaultFloorLocationId,
  floorLocations,
  resolveFloorLocationId,
} from "@/lib/wms-location";

function location(
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
    archived_at: is_archived ? "2026-01-02T00:00:00Z" : null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

const kramerville = location("loc-k", "Kramerville", "warehouse");
const bedfordview = location("loc-b", "Bedfordview", "showroom");
const pretoria = location("loc-p", "Pretoria", "showroom");

describe("wms-location", () => {
  it("lists active warehouse and showroom locations sorted by type then name", () => {
    const floor = floorLocations([pretoria, bedfordview, kramerville]);
    expect(floor?.map((entry) => entry.id)).toEqual(["loc-k", "loc-b", "loc-p"]);
  });

  it("omits archived locations", () => {
    const archived = location("loc-x", "Closed", "warehouse", true);
    const floor = floorLocations([kramerville, archived, bedfordview]);
    expect(floor?.map((entry) => entry.id)).toEqual(["loc-k", "loc-b"]);
  });

  it("defaults to the first warehouse when nothing is stored", () => {
    const floor = floorLocations([kramerville, bedfordview]);
    expect(floor).not.toBeNull();
    if (!floor) {
      return;
    }
    expect(defaultFloorLocationId(floor)).toBe("loc-k");
    expect(resolveFloorLocationId(floor, null)).toBe("loc-k");
  });

  it("restores a stored selection for any active floor location", () => {
    const floor = floorLocations([kramerville, bedfordview, pretoria]);
    expect(floor).not.toBeNull();
    if (!floor) {
      return;
    }
    expect(resolveFloorLocationId(floor, "loc-p")).toBe("loc-p");
  });

  it("falls back when a stored location was archived or renamed away", () => {
    const floor = floorLocations([kramerville, bedfordview]);
    expect(floor).not.toBeNull();
    if (!floor) {
      return;
    }
    expect(resolveFloorLocationId(floor, "loc-missing")).toBe("loc-k");
  });
});
