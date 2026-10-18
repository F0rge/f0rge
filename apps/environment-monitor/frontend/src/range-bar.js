// Geometry for the metric range bars. Comfort edges come from comfort.js
// (the same 20–24°C and 40–60% the Comfort % uses). "Far" is a fixed step
// past those edges: 3°C or 10 percentage points. In-band is one colour for
// both metrics; amber and red are only the parts outside the band.

export const FAR_BEYOND_TEMP_C = 3;
export const FAR_BEYOND_HUMIDITY_PCT = 10;

// Room on either side of the comfort band and this period's min/max.
// A fixed 15–35°C track turned a 2° spread into a sliver.
export const TEMP_SCALE_PAD = 1;
export const HUMIDITY_SCALE_PAD = 3;

const IN_BAND_TONE = 'success';
const MIN_PIECE_PCT = 0.8;

export function domainFor(comfortMin, comfortMax, dataMin, dataMax, pad) {
  const min = Math.min(comfortMin, dataMin) - pad;
  const max = Math.max(comfortMax, dataMax) + pad;
  if (!(max > min)) return { min: comfortMin - pad, max: comfortMax + pad };
  return { min, max };
}

export function percentAlong(value, domain) {
  const span = domain.max - domain.min;
  if (!(span > 0)) return 0;
  const pct = ((value - domain.min) / span) * 100;
  return Math.min(100, Math.max(0, pct));
}

// Amber within `far` of the band, red beyond that, success inside.
export function toneAt(value, comfortMin, comfortMax, far) {
  if (value < comfortMin - far || value > comfortMax + far) return 'danger';
  if (value < comfortMin || value > comfortMax) return 'attention';
  return IN_BAND_TONE;
}

export function spanPieces(min, max, comfortMin, comfortMax, far) {
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
      tone: toneAt((from + to) / 2, comfortMin, comfortMax, far),
    });
  }
  if (pieces.length === 0) {
    pieces.push({
      from: lo,
      to: hi,
      tone: toneAt(lo, comfortMin, comfortMax, far),
    });
  }
  return pieces;
}

export function layoutMetricBar({
  min, max, average, comfortMin, comfortMax, far, pad,
}) {
  const lo = Math.min(min, max);
  const hi = Math.max(min, max);
  const domain = domainFor(
    comfortMin,
    comfortMax,
    Math.min(lo, average),
    Math.max(hi, average),
    pad,
  );
  const toPct = (value) => percentAlong(value, domain);
  const pieces = spanPieces(lo, hi, comfortMin, comfortMax, far).map((piece) => ({
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
