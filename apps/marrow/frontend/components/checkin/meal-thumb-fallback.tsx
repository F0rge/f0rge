'use client'

import { ImageOff } from 'lucide-react'
import { cn } from '@f0rge/ui'
import {
  MEAL_LIBRARY_LABEL,
  MEAL_PHOTO_MISSING_LABEL,
  MealIconThumb,
} from '@/components/checkin/meal-icon-thumb'

const MEDIA_BADGE_CLASS =
  'absolute left-1.5 top-1.5 rounded-full bg-background/90 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-muted-foreground ring-1 ring-border'

interface MealThumbFallbackProps {
  kind: 'library' | 'missing'
  iconKey?: string | null
  size?: 'sm' | 'md' | 'lg'
  className?: string
  /** Check-in tile only. Other surfaces stay unlabeled. */
  showBadge?: boolean
}

export function MealThumbFallback({
  kind,
  iconKey,
  size = 'lg',
  className,
  showBadge = false,
}: MealThumbFallbackProps) {
  const library = kind === 'library'
  return (
    <div className={cn('relative size-full', className)}>
      {library ? (
        <MealIconThumb
          iconKey={iconKey ?? 'bowl'}
          size={size}
          className="size-full rounded-none"
        />
      ) : (
        <div
          className="flex size-full items-center justify-center bg-muted"
          role="img"
          aria-label={MEAL_PHOTO_MISSING_LABEL}
        >
          <ImageOff className="size-8 text-muted-foreground" aria-hidden />
        </div>
      )}
      {showBadge && (
        <span className={MEDIA_BADGE_CLASS}>
          {library ? MEAL_LIBRARY_LABEL : MEAL_PHOTO_MISSING_LABEL}
        </span>
      )}
    </div>
  )
}
