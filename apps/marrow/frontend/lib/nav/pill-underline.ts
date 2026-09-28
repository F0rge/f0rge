/** Stroke that rides the pill border. Outer edge of the stroke is the pill edge. */
export const PILL_UNDERLINE_STROKE = 3

export interface UnderlineDash {
  dasharray: string
  dashoffset: number
  start: number
  end: number
  total: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

/**
 * Bottom silhouette of a pill, from the left side around the bottom to the right side.
 * `inset` is half the stroke so a centered stroke's outer edge meets the border box.
 */
export function pillBottomPath(width: number, height: number, inset: number): string {
  const radius = height / 2 - inset
  if (radius <= 0 || width <= height) {
    const y = Math.max(height - inset, 0)
    return `M ${inset} ${y} L ${Math.max(width - inset, inset)} ${y}`
  }
  const right = width - inset
  const bottom = height - inset
  return `M ${inset} ${inset + radius} A ${radius} ${radius} 0 0 0 ${inset + radius} ${bottom} L ${right - radius} ${bottom} A ${radius} ${radius} 0 0 0 ${right} ${inset + radius}`
}

/** Distance along the bottom border from the left side to horizontal position `x`. */
export function borderLengthAt(
  x: number,
  width: number,
  height: number,
  stroke: number = PILL_UNDERLINE_STROKE,
): number {
  const radius = height / 2
  const innerRadius = radius - stroke / 2
  const px = clamp(x, 0, width)
  if (innerRadius <= 0 || width <= height) return px

  const flat = width - 2 * radius
  const quarter = (Math.PI * innerRadius) / 2
  if (px <= radius) {
    const theta = Math.acos(clamp(px / radius - 1, -1, 1))
    return innerRadius * (Math.PI - theta)
  }
  if (px >= width - radius) {
    const theta = Math.acos(clamp((px - (width - radius)) / radius, -1, 1))
    return quarter + flat + innerRadius * (Math.PI / 2 - theta)
  }
  return quarter + (px - radius)
}

/**
 * Horizontal span of the active tab along the pill's outer edge.
 * The first tab owns the left cap; the last tab owns the right cap.
 */
export function fullCornerSpan(
  index: number,
  width: number,
  padLeft: number,
  padRight: number,
  count: number,
): { x0: number; x1: number } {
  const inner = Math.max(width - padLeft - padRight, 0)
  const tabW = count > 0 ? inner / count : inner
  let x0 = padLeft + tabW * index
  let x1 = x0 + tabW
  if (index <= 0) x0 = 0
  if (index >= count - 1) x1 = width
  return { x0, x1 }
}

export function underlineDash(
  x0: number,
  x1: number,
  width: number,
  height: number,
  stroke: number = PILL_UNDERLINE_STROKE,
): UnderlineDash {
  const start = borderLengthAt(x0, width, height, stroke)
  const end = borderLengthAt(Math.max(x1, x0), width, height, stroke)
  const total = borderLengthAt(width, width, height, stroke)
  const seg = Math.max(0, end - start)
  const gap = Math.max(total - seg, 0.001)
  return { dasharray: `${seg} ${gap}`, dashoffset: -start, start, end, total }
}

export function collapsedUnderlineDash(
  centerX: number,
  width: number,
  height: number,
  stroke: number = PILL_UNDERLINE_STROKE,
): UnderlineDash {
  const at = borderLengthAt(centerX, width, height, stroke)
  const total = borderLengthAt(width, width, height, stroke)
  return { dasharray: `0 ${Math.max(total, 0.001)}`, dashoffset: -at, start: at, end: at, total }
}
