'use client'

import { useEffect, useState } from 'react'

/** Tailwind `lg` breakpoint — matches grid layout at 1024px. */
export const LG_DESKTOP_QUERY = '(min-width: 1024px)'

export function useMediaQuery(query: string): boolean {
  // Always false until mount so SSR and the first client render agree.
  const [matches, setMatches] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia(query)
    const sync = () => setMatches(mq.matches)
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [query])

  return matches
}
