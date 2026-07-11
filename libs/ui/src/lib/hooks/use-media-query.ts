'use client'

import { useSyncExternalStore } from 'react'

/** Tailwind `lg` breakpoint — matches grid layout at 1024px. */
export const LG_DESKTOP_QUERY = '(min-width: 1024px)'

function subscribe(query: string, onStoreChange: () => void): () => void {
  const mq = window.matchMedia(query)
  mq.addEventListener('change', onStoreChange)
  return () => mq.removeEventListener('change', onStoreChange)
}

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onStoreChange) => subscribe(query, onStoreChange),
    () => window.matchMedia(query).matches,
    () => false,
  )
}
