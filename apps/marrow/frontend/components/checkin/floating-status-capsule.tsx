'use client'

import { useState, useEffect } from 'react'
import { Loader2, Check, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AutosaveStatus } from '@/lib/hooks/use-autosave-entry'

interface FloatingStatusCapsuleProps {
  date: string
  status: AutosaveStatus
  lastSavedAt: number | null
  errorMessage: string | null
  onRetry: () => void
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

function formatElapsed(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  if (seconds < 10) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes === 1) return '1 min ago'
  return `${minutes} min ago`
}

function useReducedMotion(): boolean {
  // Initialise from matchMedia immediately so we never render a frame
  // with the wrong value. The effect only subscribes to future changes.
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
  status,
  lastSavedAt,
  errorMessage,
  onRetry,
  sentinelRef,
  hidden = false,
}: FloatingStatusCapsuleProps) {
  const [sentinelGone, setSentinelGone] = useState(false)
  // True once the header has scrolled out of view at least once —
  // prevents the capsule from appearing on first paint before any scroll.
  const [hasEverScrolledPast, setHasEverScrolledPast] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const reducedMotion = useReducedMotion()

  // IntersectionObserver: watch the sentinel (the page header).
  // When the sentinel is fully out of view, sentinelGone = true.
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        const gone = !entry.isIntersecting
        if (gone) setHasEverScrolledPast(true)
        setSentinelGone(gone)
      },
      // threshold: 0 means the callback fires when even 1px of the sentinel
      // is visible (intersecting) or when it's fully gone (not intersecting).
      { threshold: 0 },
    )

    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [sentinelRef])

  // Tick the clock while in saved state so elapsed time updates live.
  useEffect(() => {
    if (status !== 'saved') return
    const interval = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(interval)
  }, [status])

  // Don't render the capsule until the user has scrolled past the header
  // at least once, AND the sentinel is currently out of view, AND not hidden.
  const isVisible = sentinelGone && hasEverScrolledPast && !hidden

  // Don't render anything at all while idle and invisible — nothing to show.
  if (status === 'idle' && !isVisible) return null

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
        // Apply transforms inline so they work reliably with Tailwind's
        // translate utilities being purged by the build step.
        transform: isVisible
          ? 'translateX(-50%) translateY(0)'
          : reducedMotion
            ? 'translateX(-50%) translateY(0)'
            : 'translateX(-50%) translateY(-12px)',
        opacity: isVisible ? 1 : 0,
        transition: reducedMotion
          ? 'opacity 220ms ease'
          : 'opacity 220ms ease, transform 280ms cubic-bezier(.2,.8,.2,1)',
      }}
      className={cn(
        'flex items-center gap-2.5 rounded-full px-3.5 py-1.5 text-xs',
        'border border-foreground/10',
        'shadow-[0_8px_24px_-8px_rgba(0,0,0,0.12),0_2px_4px_rgba(0,0,0,0.04)]',
        'backdrop-blur-md',
        'bg-white/72 dark:bg-background/80',
      )}
    >
      <span className="shrink-0 font-semibold text-foreground">{shortDate}</span>
      {status !== 'idle' && (
        <>
          <span className="text-border/80" aria-hidden="true">
            ·
          </span>
          <StatusContent status={status} lastSavedAt={lastSavedAt} errorMessage={errorMessage} onRetry={onRetry} now={now} />
        </>
      )}
    </div>
  )
}

interface StatusContentProps {
  status: AutosaveStatus
  lastSavedAt: number | null
  errorMessage: string | null
  onRetry: () => void
  now: number
}

// Module-scope component — avoids react-hooks/static-components lint error.
function StatusContent({ status, lastSavedAt, errorMessage, onRetry, now }: StatusContentProps) {
  if (status === 'saving') {
    return (
      <span className="inline-flex items-center gap-1.5 text-muted-foreground">
        <Loader2 className="size-3 animate-spin" />
        <span>Saving&hellip;</span>
      </span>
    )
  }

  if (status === 'saved') {
    const elapsed = lastSavedAt ? now - lastSavedAt : 0
    return (
      <span className="inline-flex items-center gap-1.5 text-green-700 dark:text-green-400">
        <Check className="size-3" strokeWidth={3} />
        <span>Saved {formatElapsed(elapsed)}</span>
      </span>
    )
  }

  if (status === 'error') {
    return (
      <button
        type="button"
        title={errorMessage ?? undefined}
        onClick={onRetry}
        className="inline-flex items-center gap-1.5 font-medium text-amber-700 dark:text-amber-400"
      >
        <AlertTriangle className="size-3" />
        <span>Couldn&apos;t save &mdash; Retry</span>
      </button>
    )
  }

  // idle / blocked: render nothing inside the capsule.
  // (The capsule itself is already hidden when idle via the isVisible gate.)
  return null
}
