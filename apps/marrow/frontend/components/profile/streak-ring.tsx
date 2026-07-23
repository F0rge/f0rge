import { Flame } from 'lucide-react'
import { UserAvatar } from '@/components/account/user-avatar'

interface StreakRingProps {
  streak: number
}

/** Avatar with optional streak-flame badge. */
export function StreakRing({ streak }: StreakRingProps) {
  return (
    <div
      role="img"
      aria-label={streak > 0 ? `Profile avatar, ${streak}-day streak` : 'Profile avatar'}
      className="relative size-[72px] flex-none"
    >
      <UserAvatar size="lg" />
      {streak > 0 && (
        <span className="absolute -right-0.5 bottom-0 flex items-center gap-0.5 rounded-full bg-card px-1.5 py-0.5 text-[10.5px] font-bold tabular-nums shadow-sm ring-1 ring-foreground/10">
          <Flame className="size-[11px]" style={{ color: 'var(--marrow-nucleus)' }} aria-hidden />
          {streak}
        </span>
      )}
    </div>
  )
}
