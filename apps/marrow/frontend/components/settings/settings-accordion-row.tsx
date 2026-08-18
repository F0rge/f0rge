'use client'

/**
 * SettingsAccordionRow — a /settings list entry that expands inline.
 *
 * Header mirrors SettingsLinkRow; chevron rotates 90° when open and the
 * children (an existing settings section component) render below, unchanged.
 * Each row keeps independent open state.
 */

import { type ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@f0rge/ui'
import { IconWell } from '@/components/shared/color-artifact'

interface SettingsAccordionRowProps {
  /** 16px icon rendered in a 36px chromatic well. */
  icon: ReactNode
  title: string
  description: string
  children: ReactNode
}

export function SettingsAccordionRow({ icon, title, description, children }: SettingsAccordionRowProps) {
  return (
    <Accordion>
      <AccordionItem value="settings-row" className="border-0">
        <AccordionTrigger
          className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-muted/50 hover:no-underline active:bg-muted [&_[data-slot=accordion-trigger-icon]]:hidden"
        >
          <IconWell>{icon}</IconWell>
          <div className="min-w-0 flex-1">
            <span className="text-sm font-medium">{title}</span>
            <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{description}</p>
          </div>
          <ChevronRight
            className="size-4 shrink-0 text-muted-foreground transition-transform group-aria-expanded/accordion-trigger:rotate-90"
          />
        </AccordionTrigger>
        <AccordionContent className="border-t border-muted px-4 py-4">
          {children}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
