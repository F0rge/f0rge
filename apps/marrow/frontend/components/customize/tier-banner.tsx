import { Lock, List, Sparkles } from 'lucide-react'
import { cn } from '@f0rge/ui'
import { tierBannerClass } from '@/lib/ui/status'
import type { Tier } from './tier-pill'

interface TierBannerProps {
  tier: Tier
  children: React.ReactNode
}

const TIER_ICONS: Record<Tier, React.ElementType> = {
  core: Lock,
  catalog: List,
  custom: Sparkles,
}

export function TierBanner({ tier, children }: TierBannerProps) {
  const { wrapperClass, iconClass } = tierBannerClass[tier]
  const Icon = TIER_ICONS[tier]

  return (
    <div className={cn('flex gap-2 rounded-md border p-2.5 mb-4', wrapperClass)}>
      <Icon className={cn('size-4 shrink-0 mt-0.5', iconClass)} />
      <p className="text-[11px] leading-snug text-muted-foreground">{children}</p>
    </div>
  )
}
