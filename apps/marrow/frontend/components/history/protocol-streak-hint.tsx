'use client'

import Link from 'next/link'
import { Flame } from 'lucide-react'
import { useProtocol } from '@/lib/api/hooks'
import { formatLocalDate, cn } from '@f0rge/ui'
import { statusPill, statusText } from '@/lib/ui/status'

interface ProtocolStreakHintProps {
  /** Currently viewed month in YYYY-MM form. */
  month: string
}

function getCurrentMonth(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

export function ProtocolStreakHint({ month }: ProtocolStreakHintProps) {
  const today = formatLocalDate(new Date())
  const { data: protocol } = useProtocol(today)

  if (!protocol || protocol.today.doses_planned === 0) return null

  const { streak, best_streak } = protocol
  const isCurrentMonth = month === getCurrentMonth()

  if (streak === 0 && !isCurrentMonth) return null

  return (
    <Link
      href="/treatments"
      className={cn(
        'mb-3 flex items-center gap-2 text-xs transition-colors hover:text-foreground',
        streak > 0 ? statusText.warn : 'text-muted-foreground',
      )}
    >
      <Flame
        className={cn('size-3.5 shrink-0', streak > 0 && cn('fill-warn', statusText.warn))}
        aria-hidden
      />
      {streak > 0 ? (
        <>
          <span>{streak}-day protocol streak</span>
          {best_streak > streak && (
            <span className={cn('rounded-full px-1.5 py-px text-xs', statusPill.warn)}>
              Best: {best_streak}
            </span>
          )}
        </>
      ) : (
        <span>Log today&apos;s doses to start a streak</span>
      )}
    </Link>
  )
}
