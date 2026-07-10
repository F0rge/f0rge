import { Lock, List, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Tier } from './tier-pill'

interface TierBannerProps {
  tier: Tier
  children: React.ReactNode
}

const TIER_CONFIG: Record<Tier, {
  wrapperClass: string
  iconClass: string
  Icon: React.ElementType
}> = {
  core: {
    wrapperClass: 'bg-zinc-50 border-zinc-100 dark:bg-zinc-900/40 dark:border-zinc-800',
    iconClass: 'text-zinc-400 dark:text-zinc-500',
    Icon: Lock,
  },
  catalog: {
    wrapperClass: 'bg-blue-50 border-blue-100 dark:bg-blue-950/40 dark:border-blue-900',
    iconClass: 'text-blue-500 dark:text-blue-400',
    Icon: List,
  },
  custom: {
    wrapperClass: 'bg-emerald-50 border-emerald-100 dark:bg-emerald-950/40 dark:border-emerald-900',
    iconClass: 'text-emerald-500 dark:text-emerald-400',
    Icon: Sparkles,
  },
}

export function TierBanner({ tier, children }: TierBannerProps) {
  const { wrapperClass, iconClass, Icon } = TIER_CONFIG[tier]

  return (
    <div className={cn('flex gap-2 rounded-md border p-2.5 mb-4', wrapperClass)}>
      <Icon className={cn('size-4 shrink-0 mt-0.5', iconClass)} />
      <p className="text-[11px] leading-snug text-muted-foreground">{children}</p>
    </div>
  )
}
