"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { listLocationBins, type LocationBin } from "@/lib/api";
import { activeBins, defaultBinId } from "@/lib/bin-helpers";

export function useLocationBins(locationId: string) {
  const [bins, setBins] = useState<LocationBin[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!locationId) {
      setBins([]);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setBins(await listLocationBins(locationId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load bins.");
      setBins([]);
    } finally {
      setLoading(false);
    }
  }, [locationId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const active = useMemo(() => activeBins(bins), [bins]);
  const defaultId = useMemo(() => defaultBinId(bins), [bins]);

  return { bins, activeBins: active, defaultBinId: defaultId, loading, error, reload };
}
