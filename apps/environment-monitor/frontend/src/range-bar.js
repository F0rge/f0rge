// Geometry for the metric range bars. Comfort edges come from comfort.js
// (the same 20–24°C and 40–60% the Comfort % uses). "Far" is a fixed step
// past those edges: 3°C or 10 percentage points.

export const FAR_BEYOND_TEMP_C = 3;
export const FAR_BEYOND_HUMIDITY_PCT = 10;

// Fixed tracks, wide enough that the comfort band and the amber margin on
// either side both sit on the bar. The domain grows only when this period's
// readings fall outside.
export const TEMP_TRACK = { min: 15, max: 35 };
export const HUMIDITY_TRACK = { min: 20, max: 80 };

const MIN_PIECE_PCT = 0.8;

export function domainFor(track, dataMin, dataMax) {
  const min = Math.min(track.min, dataMin);
  const max = Math.max(track.max, dataMax);
  if (!(max > min)) return { min: track.min, max: track.max };
  return { min, max };
}

export function percentAlong(value, domain) {
  const span = domain.max - domain.min;
  if (!(span > 0)) return 0;
  const pct = ((value - domain.min) / span) * 100;
  return Math.min(100, Math.max(0, pct));
}

// Amber within `far` of the band, red beyond that, `inBandTone` inside.
export function toneAt(value, comfortMin, comfortMax, far, inBandTone) {
  if (value < comfortMin - far || value > comfortMax + far) return 'danger';
  if (value < comfortMin || value > comfortMax) return 'attention';
  return inBandTone;
}

export function spanPieces(min, max, comfortMin, comfortMax, far, inBandTone) {
  const lo = Math.min(min, max);
  const hi = Math.max(min, max);
  const cuts = [comfortMin - far, comfortMin, comfortMax, comfortMax + far]
    .filter((cut) => cut > lo && cut < hi)
    .sort((a, b) => a - b);
  const points = [lo, ...cuts, hi];
  const pieces = [];
  for (let i = 0; i < points.length - 1; i++) {
    const from = points[i];
    const to = points[i + 1];
    if (to <= from) continue;
    pieces.push({
      from,
      to,
      tone: toneAt((from + to) / 2, comfortMin, comfortMax, far, inBandTone),
    });
  }
  if (pieces.length === 0) {
    pieces.push({
      from: lo,
      to: hi,
      tone: toneAt(lo, comfortMin, comfortMax, far, inBandTone),
    });
  }
  return pieces;
}

export function layoutMetricBar({
  min, max, average, comfortMin, comfortMax, far, track, inBandTone,
}) {
  const lo = Math.min(min, max);
  const hi = Math.max(min, max);
  const domain = domainFor(track, Math.min(lo, average), Math.max(hi, average));
  const toPct = (value) => percentAlong(value, domain);
  const pieces = spanPieces(lo, hi, comfortMin, comfortMax, far, inBandTone).map((piece) => ({
    left: toPct(piece.from),
    width: Math.max(0, toPct(piece.to) - toPct(piece.from)),
    tone: piece.tone,
  }));
  if (pieces.length === 1 && pieces[0].width < MIN_PIECE_PCT) {
    const mid = pieces[0].left + pieces[0].width / 2;
    pieces[0].left = Math.min(100 - MIN_PIECE_PCT, Math.max(0, mid - MIN_PIECE_PCT / 2));
    pieces[0].width = MIN_PIECE_PCT;
  }
  const bandLeft = toPct(comfortMin);
  return {
    bandLeft,
    bandWidth: Math.max(0, toPct(comfortMax) - bandLeft),
    averageLeft: toPct(average),
    pieces,
  };
}
