import type { LocationBin } from "@/lib/api";

export function parseRowCodes(input: string): string[] {
  const trimmed = input.trim().toUpperCase();
  if (!trimmed) {
    return [];
  }
  if (trimmed.includes(",")) {
    const seen = new Set<string>();
    const rows: string[] = [];
    for (const part of trimmed.split(",")) {
      const row = part.trim();
      if (!row || seen.has(row)) {
        continue;
      }
      seen.add(row);
      rows.push(row);
    }
    return rows;
  }
  const range = trimmed.match(/^([A-Z])\s*[–-]\s*([A-Z])$/);
  if (range) {
    const start = range[1].charCodeAt(0);
    const end = range[2].charCodeAt(0);
    const lo = Math.min(start, end);
    const hi = Math.max(start, end);
    const rows: string[] = [];
    for (let code = lo; code <= hi; code += 1) {
      rows.push(String.fromCharCode(code));
    }
    return rows;
  }
  return [trimmed];
}

export function activeBins(bins: LocationBin[]): LocationBin[] {
  return bins.filter((bin) => !bin.is_archived);
}

export function defaultBinId(bins: LocationBin[]): string {
  return activeBins(bins).find((bin) => bin.is_default)?.id ?? "";
}

export function matchBinByCode(bins: LocationBin[], code: string): LocationBin | undefined {
  const trimmed = code.trim().toUpperCase();
  if (!trimmed) {
    return undefined;
  }
  return activeBins(bins).find((bin) => bin.code.toUpperCase() === trimmed);
}

export function sortLocationBins(bins: LocationBin[]): LocationBin[] {
  return [...bins].sort((a, b) => {
    if (a.is_archived !== b.is_archived) {
      return a.is_archived ? 1 : -1;
    }
    if (a.is_default !== b.is_default) {
      return a.is_default ? -1 : 1;
    }
    return a.code.localeCompare(b.code);
  });
}

export function optionalMovementBinId(selectedId: string, defaultId: string): string | undefined {
  if (!selectedId || selectedId === defaultId) {
    return undefined;
  }
  return selectedId;
}
