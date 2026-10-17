import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'

import { DietRiskSection } from './diet-risk-section'
import type { DietTagCatalogItem, Entry, PhotoSignal } from '@/lib/api/types'

const october17: PhotoSignal = {
  flags: ['high-fodmap', 'dairy', 'gluten', 'high-histamine'],
  scores: {
    histamine_load: 8,
    fodmap_count: 1,
    gluten_count: 1,
    dairy_count: 2,
  },
  sources: {
    'high-fodmap': ['spaghetti'],
    dairy: ['parmesan', 'cream'],
    gluten: ['spaghetti'],
    'high-histamine': ['bacon', 'parmesan'],
  },
}

const catalog: DietTagCatalogItem[] = [
  { id: 1, key: 'high-fodmap', label: 'High-FODMAP', archived: false, sort_order: 1 },
  { id: 2, key: 'dairy', label: 'Dairy', archived: false, sort_order: 2 },
  { id: 3, key: 'gluten', label: 'Gluten', archived: false, sort_order: 3 },
  { id: 4, key: 'high-histamine', label: 'High-histamine', archived: false, sort_order: 4 },
]

function renderSection() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const entry = { photo_signal: october17 } as Entry
  const photos = [{ id: 785 }, { id: 786 }] as Entry['photos']
  return renderToStaticMarkup(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(DietRiskSection, {
        existingEntry: entry,
        existingPhotos: photos,
        dietRisk: '',
        onToggle: () => {},
        catalog,
        catalogLoading: false,
      }),
    ),
  )
}

describe('DietRiskSection pills', () => {
  it('shows a distinct ingredient count on every pill, including high-histamine', () => {
    const html = renderSection()

    expect(html).toContain('High-FODMAP')
    expect(html).toContain('High-histamine')
    expect(html).toContain('High-FODMAP: spaghetti')
    expect(html).toContain('High-histamine: bacon, parmesan')
    expect(html).toContain('2 photos')
    expect(html).toContain('6 ingredients')
    expect(html).toContain('title="2 ingredients: bacon, parmesan"')
    expect(html).not.toContain('Σ histamine_score')
    expect(html).not.toContain('title="8 ingredients')
    expect(html).not.toContain('>8<')
  })
})
