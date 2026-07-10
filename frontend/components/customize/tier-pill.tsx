import { cn } from '@/lib/utils'

export type Tier = 'core' | 'catalog' | 'custom'

interface TierPillProps {
  tier: Tier
  className?: string
}

const TIER_STYLES: Record<Tier, string> = {
  core:    'bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-400',
  catalog: 'bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400',
  custom:  'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400',
}

const TIER_LABELS: Record<Tier, string> = {
  core:    'Core',
  catalog: 'Catalog',
  custom:  'Custom',
}

export function TierPill({ tier, className }: TierPillProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-1.5 py-px',
        'text-[9px] font-bold uppercase tracking-widest',
        TIER_STYLES[tier],
        className,
      )}
    >
      {TIER_LABELS[tier]}
    </span>
  )
}
