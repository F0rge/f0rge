import { describe, expect, it } from "vitest";

import type { Location } from "@/lib/api";
import {
  defaultFloorLocationId,
  floorLocations,
  resolveFloorLocationId,
} from "@/lib/wms-location";

const kramerville: Location = {
  id: "loc-k",
  name: "Kramerville",
  type: "warehouse",
  is_archived: false,
  archived_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const bedfordview: Location = {
  id: "loc-b",
  name: "Bedfordview",
  type: "showroom",
  is_archived: false,
  archived_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("wms-location", () => {
  it("resolves the two floor locations", () => {
    const floor = floorLocations([kramerville, bedfordview]);
    expect(floor?.kramerville.id).toBe("loc-k");
    expect(floor?.bedfordview.id).toBe("loc-b");
  });

  it("defaults to Kramerville when nothing is stored", () => {
    const floor = floorLocations([kramerville, bedfordview]);
    expect(floor).not.toBeNull();
    if (!floor) {
      return;
    }
    expect(defaultFloorLocationId(floor)).toBe("loc-k");
    expect(resolveFloorLocationId(floor, null)).toBe("loc-k");
  });

  it("restores a stored Bedfordview selection", () => {
    const floor = floorLocations([kramerville, bedfordview]);
    expect(floor).not.toBeNull();
    if (!floor) {
      return;
    }
    expect(resolveFloorLocationId(floor, "loc-b")).toBe("loc-b");
  });
});
