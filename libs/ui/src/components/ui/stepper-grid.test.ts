import { describe, expect, it } from 'vitest'

import { stepTargets } from './stepper-grid'

describe('stepTargets', () => {
  it('moves by one without a step, exactly as before', () => {
    for (let value = 0; value <= 10; value++) {
      expect(stepTargets(value, 0, 10)).toEqual({ down: value > 0 ? value - 1 : null, up: value < 10 ? value + 1 : null })
    }
  })

  it('moves by the step from the minimum', () => {
    expect(stepTargets(2, 2, 8, 2)).toEqual({ down: null, up: 4 })
    expect(stepTargets(4, 2, 8, 2)).toEqual({ down: 2, up: 6 })
    expect(stepTargets(4, 4, 12, 2)).toEqual({ down: null, up: 6 })
  })

  it('never overshoots max: the last step that fits is the end', () => {
    expect(stepTargets(4, 2, 5, 2)).toEqual({ down: 2, up: null })
    expect(stepTargets(6, 6, 11, 6)).toEqual({ down: null, up: null })
  })

  it('snaps an off-grid value back onto the grid', () => {
    expect(stepTargets(5, 2, 10, 2)).toEqual({ down: 4, up: 6 })
    expect(stepTargets(3, 2, 10, 2)).toEqual({ down: 2, up: 4 })
  })

  it('lets a value above max come down, but not go further up', () => {
    expect(stepTargets(6, 2, 4, 2)).toEqual({ down: 4, up: null })
  })

  it('treats an invalid step as 1', () => {
    expect(stepTargets(3, 0, 10, 0)).toEqual({ down: 2, up: 4 })
    expect(stepTargets(3, 0, 10, 1.5)).toEqual({ down: 2, up: 4 })
  })
})
