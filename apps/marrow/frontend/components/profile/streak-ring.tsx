import { Flame } from 'lucide-react'
import { UserAvatar } from '@/components/account/user-avatar'

interface StreakRingProps {
  weekDays: boolean[]
  streak: number
}

/** Avatar wearing this week's check-in ratio as a ring, plus a streak-flame badge. */
export function StreakRing({ weekDays, streak }: StreakRingProps) {
  const done = weekDays.filter(Boolean).length
  const pct = Math.round((done / 7) * 100)

  return (
    <div
      role="img"
      aria-label={`${done} of 7 check-in days this week${streak > 0 ? `, ${streak}-day streak` : ''}`}
      className="relative size-[92px] flex-none"
    >
      <svg viewBox="0 0 92 92" className="absolute inset-0 -rotate-90">
        <circle cx="46" cy="46" r="43" fill="none" strokeWidth="4.5" className="stroke-muted" />
        {/* Track only at 0: a zero-length dash under a round cap paints a dot, not nothing. */}
        {pct > 0 && (
          <circle
            cx="46"
            cy="46"
            r="43"
            fill="none"
            strokeWidth="4.5"
            strokeLinecap="round"
            pathLength={100}
            strokeDasharray={`${pct} 100`}
            style={{ stroke: 'var(--marrow-nucleus)' }}
          />
        )}
      </svg>
      <UserAvatar size="lg" className="absolute inset-[10px]" />
      {streak > 0 && (
        <span className="absolute -right-0.5 bottom-0 flex items-center gap-0.5 rounded-full bg-card px-1.5 py-0.5 text-[10.5px] font-bold tabular-nums shadow-sm ring-1 ring-foreground/10">
          <Flame className="size-[11px]" style={{ color: 'var(--marrow-nucleus)' }} aria-hidden />
          {streak}
        </span>
      )}
    </div>
  )
}
