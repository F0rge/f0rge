"use client";

import { useCallback, useMemo, useState } from "react";

import { isActiveLocation, type Location } from "@/lib/api";

export const WMS_LOCATION_STORAGE_KEY = "vellano-wms-location-id";

export function floorLocations(locations: Location[]): Location[] {
  return locations.filter(isActiveLocation);
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

export function defaultFloorLocationId(floor: Location[]): string {
  return floor.find((location) => location.type === "warehouse")?.id ?? floor[0]?.id ?? "";
}

export function resolveFloorLocationId(floor: Location[], stored: string | null): string {
  if (stored && floor.some((location) => location.id === stored)) {
    return stored;
  }
  return defaultFloorLocationId(floor);
}

export function useWmsFloorLocation(locations: Location[]) {
  const floor = useMemo(() => floorLocations(locations), [locations]);
  const defaultLocationId = useMemo(() => {
    if (floor.length === 0) {
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
