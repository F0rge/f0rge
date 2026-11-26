/**
 * The values a Stepper's minus and plus buttons move to, or null when that
 * button is disabled. Values stay on the grid min, min + step, min + 2·step…
 * and plus never passes max. With step 1 this is value - 1 / value + 1.
 */
export function stepTargets(value: number, min: number, max: number, step = 1): { down: number | null; up: number | null } {
  const size = Number.isSafeInteger(step) && step > 0 ? step : 1
  const offGrid = (((value - min) % size) + size) % size
  const down = offGrid ? value - offGrid : value - size
  const up = value - offGrid + size
  return { down: down >= min ? down : null, up: up <= max ? up : null }
}
