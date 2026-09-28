import { describe, expect, it } from 'vitest'
import {
  PILL_UNDERLINE_STROKE,
  borderLengthAt,
  collapsedUnderlineDash,
  fullCornerSpan,
  pillBottomPath,
  underlineDash,
} from './pill-underline'

const W = 292
const H = 68
const PAD = 4
const COUNT = 6

describe('pill underline', () => {
  it('draws the bottom of the pill, from the side around the corner', () => {
    const inset = PILL_UNDERLINE_STROKE / 2
    const radius = H / 2 - inset
    const path = pillBottomPath(W, H, inset)
    expect(path.startsWith(`M ${inset} ${inset + radius} A`)).toBe(true)
    expect(path).toContain(`${inset + radius} ${H - inset}`)
    expect(path.endsWith(`${W - inset} ${inset + radius}`)).toBe(true)
  })

  it('measures the left cap, the flat bottom, and the right cap', () => {
    const radius = H / 2
    const inner = radius - PILL_UNDERLINE_STROKE / 2
    const quarter = (Math.PI * inner) / 2
    const flat = W - 2 * radius
    expect(borderLengthAt(0, W, H)).toBe(0)
    expect(borderLengthAt(radius, W, H)).toBeCloseTo(quarter)
    expect(borderLengthAt(W - radius, W, H)).toBeCloseTo(quarter + flat)
    expect(borderLengthAt(W, W, H)).toBeCloseTo(quarter * 2 + flat)
  })

  it('gives Today the left corner and Profile the right corner', () => {
    const today = fullCornerSpan(0, W, PAD, PAD, COUNT)
    const history = fullCornerSpan(1, W, PAD, PAD, COUNT)
    const profile = fullCornerSpan(COUNT - 1, W, PAD, PAD, COUNT)
    const radius = H / 2

    expect(today.x0).toBe(0)
    expect(today.x1).toBeGreaterThan(radius)
    expect(history.x0).toBeGreaterThan(radius)
    expect(profile.x1).toBe(W)
    expect(profile.x0).toBeLessThan(W - radius)

    const todayDash = underlineDash(today.x0, today.x1, W, H)
    expect(todayDash.start).toBe(0)
    expect(todayDash.end).toBeGreaterThan(borderLengthAt(radius, W, H))

    const profileDash = underlineDash(profile.x0, profile.x1, W, H)
    expect(profileDash.end).toBeCloseTo(profileDash.total)
    expect(profileDash.start).toBeLessThan(borderLengthAt(W - radius, W, H))
  })

  it('keeps a middle tab on the flat bottom', () => {
    const labs = fullCornerSpan(3, W, PAD, PAD, COUNT)
    const radius = H / 2
    expect(labs.x0).toBeGreaterThan(radius)
    expect(labs.x1).toBeLessThan(W - radius)
    const dash = underlineDash(labs.x0, labs.x1, W, H)
    expect(dash.end - dash.start).toBeCloseTo(labs.x1 - labs.x0)
  })

  it('collapses to a point on the border', () => {
    const dash = collapsedUnderlineDash(W / 2, W, H)
    expect(dash.start).toBe(dash.end)
    expect(dash.dasharray.startsWith('0 ')).toBe(true)
  })
})
