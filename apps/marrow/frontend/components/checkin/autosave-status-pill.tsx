'use client'

import { useState, useEffect } from 'react'
import { Loader2, Check, AlertTriangle } from 'lucide-react'
import { cn } from '@f0rge/ui'
import type { AutosaveStatus } from '@/lib/hooks/use-autosave-entry'
import { statusPill } from '@/lib/ui/status'

interface AutosaveStatusPillProps {
  status: AutosaveStatus
  lastSavedAt: number | null
  errorMessage: string | null
  onRetry: () => void
}

function formatElapsed(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  if (seconds < 10) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes === 1) return '1 min ago'
  return `${minutes} min ago`
}

export function AutosaveStatusPill({
  status,
  lastSavedAt,
  errorMessage,
  onRetry,
}: AutosaveStatusPillProps) {
  const [now, setNow] = useState(() => Date.now())

  // Tick every second while saved so the elapsed time updates.
  useEffect(() => {
    if (status !== 'saved') return
    const interval = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(interval)
  }, [status])

  if (status === 'idle') return null

  if (status === 'saving') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
        <Loader2 className="size-3 animate-spin" />
        Saving&hellip;
      </span>
    )
  }

  if (status === 'saved') {
    const elapsed = lastSavedAt ? now - lastSavedAt : 0
    return (
      <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium', statusPill.ok)}>
        <Check className="size-3" />
        Saved {formatElapsed(elapsed)}
      </span>
    )
  }

  if (status === 'error') {
    return (
      <button
        type="button"
        title={errorMessage ?? undefined}
        onClick={onRetry}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-colors hover:bg-warn/25',
          statusPill.warn,
        )}
      >
        <AlertTriangle className="size-3" />
        Couldn&apos;t save &mdash; Retry
      </button>
    )
  }

  return null
}
