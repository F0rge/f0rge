"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { listLocationBins, type LocationBin } from "@/lib/api";
import { activeBins, defaultBinId } from "@/lib/bin-helpers";

const NO_BINS: LocationBin[] = [];

export function useLocationBins(locationId: string) {
  const client = useQueryClient();
  const queryKey = ["location-bins", { locationId }];
  const query = useQuery({
    queryKey,
    queryFn: () => listLocationBins(locationId),
    enabled: Boolean(locationId),
  });
  const bins = (locationId && !query.error && query.data) || NO_BINS;

  const active = useMemo(() => activeBins(bins), [bins]);
  const defaultId = useMemo(() => defaultBinId(bins), [bins]);

  return {
    bins,
    activeBins: active,
    defaultBinId: defaultId,
    loading: query.isFetching,
    error: locationId && query.error ? query.error.message || "Failed to load bins." : null,
    reload: () => client.invalidateQueries({ queryKey }),
  };
}
