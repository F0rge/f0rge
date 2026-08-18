import type { ReactNode } from 'react'
import { cn } from '@f0rge/ui'
import {
  CHROME_TONE,
  iconWellClass,
  sectionMarkClass,
  type ArtifactTone,
} from '@/lib/ui/status'

/**
 * Decorative colour marks. Never put these inside form controls — they read as
 * broken toggles. Pair hue with shape (WCAG 1.4.1). aria-hidden always.
 *
 * Pass a tone from `toneFromTier` when the row/card has a governance tier.
 * Otherwise mustard (`CHROME_TONE`) — never hash a title.
 */

export function IconWell({
  tone = CHROME_TONE,
  children,
  muted = false,
  className,
}: {
  tone?: ArtifactTone
  children: ReactNode
  muted?: boolean
  className?: string
}) {
  return (
    <span
      aria-hidden
      className={cn(
        'flex size-9 shrink-0 items-center justify-center rounded-[10px] [&_svg]:text-current',
        muted ? 'bg-muted text-muted-foreground' : iconWellClass[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function SectionMark({
  tone = CHROME_TONE,
  className,
}: {
  tone?: ArtifactTone
  className?: string
}) {
  return (
    <span
      className={cn('inline-flex size-3 shrink-0 items-center justify-center', className)}
      aria-hidden
    >
      <span className={cn('size-2.5', sectionMarkClass[tone])} />
    </span>
  )
}

/** Empty-state illustration — overlapping geometry, not a control. */
export function EmptyMark({ className }: { className?: string }) {
  return (
    <span
      className={cn('pointer-events-none relative mx-auto block size-14', className)}
      aria-hidden
    >
      <span className="absolute left-1 top-2 size-9 rounded-[14px] bg-chart-3" />
      <span className="absolute bottom-0 right-0 size-7 rounded-full bg-chart-1" />
      <span className="absolute right-1.5 top-0 size-3.5 rotate-45 rounded-[3px] bg-chart-5" />
    </span>
  )
}

export function EmptyBoard({
  title,
  body,
  action,
  className,
}: {
  title: string
  body: string
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      role="status"
      className={cn(
        'flex flex-col items-center rounded-xl border border-dashed border-border px-6 py-8 text-center',
        className,
      )}
    >
      <EmptyMark className="mb-4" />
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 max-w-xs text-xs leading-snug text-muted-foreground">{body}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}
