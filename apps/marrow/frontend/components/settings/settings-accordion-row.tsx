'use client'

/**
 * SettingsAccordionRow — a /settings list entry that expands inline.
 *
 * Header mirrors SettingsLinkRow; chevron rotates 90° when open and the
 * children (an existing settings section component) render below, unchanged.
 * Each row keeps independent open state.
 */

import { useId, useState, type ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { cn } from '@f0rge/ui'

interface SettingsAccordionRowProps {
  /** 16px icon element rendered in a muted 36px tile. */
  icon: ReactNode
  title: string
  description: string
  children: ReactNode
}

export function SettingsAccordionRow({ icon, title, description, children }: SettingsAccordionRowProps) {
  const [open, setOpen] = useState(false)
  const contentId = useId()

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={contentId}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-muted/50 active:bg-muted"
      >
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <span className="text-sm font-medium">{title}</span>
          <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{description}</p>
        </div>
        <ChevronRight
          className={cn('size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')}
        />
      </button>
      {open && (
        <div id={contentId} className="border-t border-muted px-4 py-4">
          {children}
        </div>
      )}
    </div>
  )
}
