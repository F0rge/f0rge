"use client";

import { useCallback, useMemo, useState } from "react";

import { isActiveLocation, type Location, type LocationType } from "@/lib/api";

export const WMS_LOCATION_STORAGE_KEY = "vellano-wms-location-id";

/** Active warehouse and showroom locations for the floor sticky bar. */
export type WmsFloorLocations = Location[];

const FLOOR_TYPE_ORDER: Record<LocationType, number> = {
  warehouse: 0,
  showroom: 1,
};

function compareFloorLocations(a: Location, b: Location): number {
  const typeDelta = FLOOR_TYPE_ORDER[a.type] - FLOOR_TYPE_ORDER[b.type];
  if (typeDelta !== 0) {
    return typeDelta;
  }
  return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
}

export function floorLocations(locations: Location[]): WmsFloorLocations | null {
  const active = locations
    .filter(isActiveLocation)
    .filter((location) => location.type === "warehouse" || location.type === "showroom")
    .sort(compareFloorLocations);
  if (active.length === 0) {
    return null;
  }
  return active;
}

function readStoredLocationId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.sessionStorage.getItem(WMS_LOCATION_STORAGE_KEY);
}

function writeStoredLocationId(id: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.sessionStorage.setItem(WMS_LOCATION_STORAGE_KEY, id);
}

export function defaultFloorLocationId(floor: WmsFloorLocations): string {
  const warehouse = floor.find((location) => location.type === "warehouse");
  return warehouse?.id ?? floor[0].id;
}

export function resolveFloorLocationId(
  floor: WmsFloorLocations,
  stored: string | null,
): string {
  if (stored && floor.some((location) => location.id === stored)) {
    return stored;
  }
  return defaultFloorLocationId(floor);
}

export function useWmsFloorLocation(locations: Location[]) {
  const floor = useMemo(() => floorLocations(locations), [locations]);
  const defaultLocationId = useMemo(() => {
    if (!floor) {
      return "";
    }
    return resolveFloorLocationId(floor, readStoredLocationId());
  }, [floor]);
  const [overrideId, setOverrideId] = useState<string | null>(null);
  const locationId = overrideId ?? defaultLocationId;

  const setLocationId = useCallback((id: string) => {
    setOverrideId(id);
    writeStoredLocationId(id);
  }, []);

  return { floor, locationId, setLocationId };
}
