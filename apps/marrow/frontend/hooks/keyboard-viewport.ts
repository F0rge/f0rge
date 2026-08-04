'use client'

import { useCallback, useEffect, useState, type RefObject } from 'react'

const FOCUS_SCROLL_DELAY_MS = 280
const DEFAULT_MIN_SPACE_PX = 120
const DEFAULT_MAX_SPACE_PX = 256

export function scrollFocusedIntoView(el: HTMLElement): void {
  window.setTimeout(() => {
    el.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, FOCUS_SCROLL_DELAY_MS)
}

export function useFocusScrollIntoView() {
  return useCallback((e: React.FocusEvent<HTMLElement>) => {
    scrollFocusedIntoView(e.currentTarget)
  }, [])
}

function measureSpaceBelow(el: HTMLElement): number {
  const viewport = window.visualViewport
  if (!viewport) return DEFAULT_MAX_SPACE_PX

  const rect = el.getBoundingClientRect()
  const visibleBottom = viewport.offsetTop + viewport.height
  return visibleBottom - rect.bottom
}

export function clampSpaceBelow(
  el: HTMLElement,
  min = DEFAULT_MIN_SPACE_PX,
  max = DEFAULT_MAX_SPACE_PX,
): number {
  return Math.min(max, Math.max(min, measureSpaceBelow(el)))
}

export function useClampedHeightBelow(
  anchorRef: RefObject<HTMLElement | null>,
  options?: { min?: number; max?: number; enabled?: boolean },
): number | undefined {
  const { min = DEFAULT_MIN_SPACE_PX, max = DEFAULT_MAX_SPACE_PX, enabled = true } = options ?? {}
  const [height, setHeight] = useState<number | undefined>(undefined)

  useEffect(() => {
    if (!enabled) return

    const update = () => {
      const el = anchorRef.current
      if (!el) return
      setHeight(clampSpaceBelow(el, min, max))
    }

    update()
    const viewport = window.visualViewport
    viewport?.addEventListener('resize', update)
    viewport?.addEventListener('scroll', update)
    window.addEventListener('resize', update)

    return () => {
      viewport?.removeEventListener('resize', update)
      viewport?.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [anchorRef, enabled, min, max])

  if (!enabled) return undefined
  return height
}
