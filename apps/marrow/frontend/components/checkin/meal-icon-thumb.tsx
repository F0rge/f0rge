'use client'

import type { LucideIcon } from 'lucide-react'
import {
  Bird,
  Cookie,
  Croissant,
  Fish,
  Flame,
  Salad,
  Sandwich,
  Soup,
  Utensils,
} from 'lucide-react'
import { cn } from '@f0rge/ui'
import type { Photo } from '@/lib/api/types'

const ICON_MAP: Record<string, LucideIcon> = {
  duck: Bird,
  sandwich: Sandwich,
  pastry: Cookie,
  fish: Fish,
  salad: Salad,
  curry: Flame,
  toast: Croissant,
  soup: Soup,
  bowl: Soup,
}

const BG_MAP: Record<string, string> = {
  duck: 'from-amber-100 to-amber-50 dark:from-amber-950/50 dark:to-amber-900/30',
  sandwich: 'from-amber-100 to-orange-50 dark:from-amber-950/50 dark:to-orange-900/30',
  pastry: 'from-rose-100 to-rose-50 dark:from-rose-950/50 dark:to-rose-900/30',
  fish: 'from-sky-100 to-sky-50 dark:from-sky-950/50 dark:to-sky-900/30',
  salad: 'from-emerald-100 to-emerald-50 dark:from-emerald-950/50 dark:to-emerald-900/30',
  curry: 'from-orange-100 to-amber-50 dark:from-orange-950/50 dark:to-amber-900/30',
  toast: 'from-amber-100 to-yellow-50 dark:from-amber-950/50 dark:to-yellow-900/30',
  soup: 'from-slate-100 to-slate-50 dark:from-slate-800/60 dark:to-slate-900/40',
  bowl: 'from-slate-100 to-slate-50 dark:from-slate-800/60 dark:to-slate-900/40',
}

const SIZE_MAP = {
  sm: { box: 'size-10', icon: 'size-4' },
  md: { box: 'size-12', icon: 'size-5' },
  lg: { box: 'size-[72px]', icon: 'size-8' },
} as const

export function photoHasImage(photo: Pick<Photo, 'has_image' | 'filename'>): boolean {
  if (photo.has_image != null) return photo.has_image
  return Boolean(photo.filename)
}

interface MealIconThumbProps {
  iconKey: string
  className?: string
  size?: keyof typeof SIZE_MAP
}

export function MealIconThumb({ iconKey, className, size = 'md' }: MealIconThumbProps) {
  const Icon = ICON_MAP[iconKey] ?? Utensils
  const bg = BG_MAP[iconKey] ?? 'from-slate-100 to-slate-50 dark:from-slate-800/60 dark:to-slate-900/40'
  const dims = SIZE_MAP[size]

  return (
    <div
      className={cn(
        'flex items-center justify-center rounded-xl bg-gradient-to-br',
        dims.box,
        bg,
        className,
      )}
      aria-hidden
    >
      <Icon className={cn(dims.icon, 'text-foreground/70')} />
    </div>
  )
}
