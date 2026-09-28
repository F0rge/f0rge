'use client'

import { useState, useEffect } from 'react'
import { cn } from '@f0rge/ui'

interface FloatingStatusCapsuleProps {
  date: string
  sentinelRef: React.RefObject<HTMLElement | null>
  hidden?: boolean
}

function formatShortDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])
  return reduced
}

export function FloatingStatusCapsule({
  date,
  sentinelRef,
  hidden = false,
}: FloatingStatusCapsuleProps) {
  const [sentinelGone, setSentinelGone] = useState(false)
  const [hasEverScrolledPast, setHasEverScrolledPast] = useState(false)
  const reducedMotion = useReducedMotion()

  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        const gone = !entry.isIntersecting
        if (gone) setHasEverScrolledPast(true)
        setSentinelGone(gone)
      },
      { threshold: 0 },
    )

    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [sentinelRef])

  const isVisible = sentinelGone && hasEverScrolledPast && !hidden

  const shortDate = formatShortDate(date)

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      style={{
        position: 'fixed',
        top: 12,
        left: '50%',
        zIndex: 40,
        pointerEvents: isVisible ? 'auto' : 'none',
        transform: isVisible
          ? 'translateX(-50%) translateY(0)'
          : reducedMotion
            ? 'translateX(-50%) translateY(0)'
            : 'translateX(-50%) translateY(-12px)',
        opacity: isVisible ? 1 : 0,
        transition: reducedMotion
          ? 'opacity 220ms ease'
          : 'opacity 320ms var(--ease-em), transform 450ms var(--ease-em)',
      }}
      className={cn(
        'flex items-center gap-2.5 rounded-full px-3.5 py-1.5 text-xs',
        'border border-border',
        'shadow-none backdrop-blur-md',
        'bg-card/80',
      )}
    >
      <span className="shrink-0 font-semibold text-foreground">{shortDate}</span>
    </div>
  )
}
