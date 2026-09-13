"use client";

import { useCallback, useMemo, useState } from "react";

import { isActiveLocation, type Location } from "@/lib/api";

export const WMS_LOCATION_STORAGE_KEY = "vellano-wms-location-id";

export type WmsFloorLocations = {
  kramerville: Location;
  bedfordview: Location;
};

export function floorLocations(locations: Location[]): WmsFloorLocations | null {
  const active = locations.filter(isActiveLocation);
  const kramerville = active.find((location) => location.name === "Kramerville");
  const bedfordview = active.find((location) => location.name === "Bedfordview");
  if (!kramerville || !bedfordview) {
    return null;
  }
  return { kramerville, bedfordview };
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
  return floor.kramerville.id;
}

export function resolveFloorLocationId(
  floor: WmsFloorLocations,
  stored: string | null,
): string {
  if (stored === floor.kramerville.id || stored === floor.bedfordview.id) {
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
