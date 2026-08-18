import { cn } from '@f0rge/ui'
import { tierPillClass, type CustomizeTier } from '@/lib/ui/status'

export type Tier = CustomizeTier

interface TierPillProps {
  tier: Tier
  className?: string
}

const TIER_LABELS: Record<Tier, string> = {
  core: 'Core',
  catalog: 'Catalog',
  custom: 'Custom',
}

export function TierPill({ tier, className }: TierPillProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-1.5 py-px',
        'text-[9px] font-bold uppercase tracking-widest',
        tierPillClass[tier],
        className,
      )}
    >
      {TIER_LABELS[tier]}
    </span>
  )
}
