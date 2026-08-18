'use client'

import { useCallback, useState } from 'react'
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
import { mealThumbBg, mealThumbBgFallback } from '@/lib/ui/status'

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

const BG_MAP = mealThumbBg

const SIZE_MAP = {
  sm: { box: 'size-10', icon: 'size-4' },
  md: { box: 'size-12', icon: 'size-5' },
  lg: { box: 'size-[72px]', icon: 'size-8' },
} as const

export function photoHasImage(photo: Pick<Photo, 'has_image' | 'filename'>): boolean {
  if (photo.has_image != null) return photo.has_image
  return Boolean(photo.filename)
}

/** Full-size image URL — lightbox / focus overlay only. */
export function photoFileSrc(photoId: number): string {
  return `/api/v1/photos/${photoId}/file`
}

/** 480px thumbnail — every tile-sized surface. */
export function photoThumbSrc(photoId: number, bust?: number): string {
  const base = `/api/v1/photos/${photoId}/thumb`
  return bust && bust > 0 ? `${base}?r=${bust}` : base
}

/**
 * One automatic retry on thumb load failure (slow first /thumb after deploy /
 * lazy generation), then give up so callers can show the bowl icon.
 */
export function useMealThumbSrc(photoId: number): {
  src: string | null
  onError: () => void
} {
  const [attempt, setAttempt] = useState(0)
  const [failed, setFailed] = useState(false)
  const onError = useCallback(() => {
    if (failed) return
    if (attempt >= 1) {
      setFailed(true)
      return
    }
    setAttempt(attempt + 1)
  }, [attempt, failed])
  return { src: failed ? null : photoThumbSrc(photoId, attempt), onError }
}

interface MealIconThumbProps {
  iconKey: string
  className?: string
  size?: keyof typeof SIZE_MAP
}

export function MealIconThumb({ iconKey, className, size = 'md' }: MealIconThumbProps) {
  const Icon = ICON_MAP[iconKey] ?? Utensils
  const bg = BG_MAP[iconKey] ?? mealThumbBgFallback
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
