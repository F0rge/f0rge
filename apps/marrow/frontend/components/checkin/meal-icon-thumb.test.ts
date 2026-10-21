import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import {
  MEAL_LIBRARY_LABEL,
  MEAL_PHOTO_MISSING_LABEL,
  mealThumbKind,
} from './meal-icon-thumb'
import { MealThumbFallback } from './meal-thumb-fallback'

describe('mealThumbKind', () => {
  it('keeps a loaded image as a photo', () => {
    expect(mealThumbKind(true, '/api/v1/photos/1/thumb')).toBe('photo')
  })

  it('treats a failed image load as missing, not a library meal', () => {
    expect(mealThumbKind(true, null)).toBe('missing')
  })

  it('treats a meal with no image as a library meal even if a src is set', () => {
    expect(mealThumbKind(false, null)).toBe('library')
    expect(mealThumbKind(false, '/api/v1/photos/1/thumb')).toBe('library')
  })
})

describe('MealThumbFallback', () => {
  it('shows the Library badge only for icon meals', () => {
    const html = renderToStaticMarkup(
      createElement(MealThumbFallback, { kind: 'library', iconKey: 'salad', showBadge: true }),
    )
    expect(html).toContain(MEAL_LIBRARY_LABEL)
    expect(html).not.toContain(MEAL_PHOTO_MISSING_LABEL)
  })

  it('shows Photo missing when the image failed to load', () => {
    const html = renderToStaticMarkup(
      createElement(MealThumbFallback, { kind: 'missing', showBadge: true }),
    )
    expect(html).toContain(MEAL_PHOTO_MISSING_LABEL)
    expect(html).not.toContain(MEAL_LIBRARY_LABEL)
    expect(html).toContain('aria-label="Photo missing"')
  })
})
